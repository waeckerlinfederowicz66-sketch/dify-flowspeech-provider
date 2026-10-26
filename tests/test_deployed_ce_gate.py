"""Offline checks of the deployed CE harness, not evidence of a deployed platform."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
import uuid
import wave

import httpx
import pytest
import yaml

from scripts.deployed_ce import check_isolation, collect, driver
from scripts.deployed_ce.collect import redact
from scripts.deployed_ce.driver import file_url, graph, terminal_event
from scripts.deployed_ce.mock_http import State, fixture_wav
from flowspeech_v1 import ApiError, V1Client, make_input

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "deployed_ce"
KEY = "isolated-fixture-credential"
REQUEST_ID = "11111111-1111-4111-8111-111111111111"


def create(state):
    body = json.dumps({"input": {"mode": "single", "text": "CE fixture " + state.case, "voiceName": "Kore"}}).encode()
    return state.handle("POST", "flowspeech.io", "/api/v1/tts/jobs",
                        {"Authorization": "Bearer " + KEY, "Idempotency-Key": REQUEST_ID}, body)


def test_fixture_wav_is_real_mono_pcm():
    with wave.open(io.BytesIO(fixture_wav())) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) == (24000, 1, 2, 9000)


def test_mock_holds_job_for_200_seconds_without_fake_sdk():
    now = [100.0]
    state = State(KEY, clock=lambda: now[0])
    state.configure("slow", 200)
    status, _, job = create(state)
    assert status == 202 and job["status"] == "queued" and job["requestId"] == REQUEST_ID
    now[0] += 199.9
    assert state.job(job["id"])["result"] is None
    now[0] += 0.1
    assert state.job(job["id"])["status"] == "success"
    assert state.job(job["id"])["result"]["url"].startswith("https://static.flowspeech.io/")


@pytest.mark.parametrize("headers", [{"Authorization": "Bearer " + KEY}, {"Cookie": "session=fixture"}])
def test_mock_storage_rejects_credentials(headers):
    status, _, _ = State(KEY).handle("GET", "static.flowspeech.io", "/audio/fixture.wav", headers, b"")
    assert status == 403


def test_credential_validation_never_creates_audio():
    state = State(KEY)
    assert state.handle("GET", "flowspeech.io", "/api/v1/quota", {}, b"")[0] == 401
    assert state.handle("GET", "flowspeech.io", "/api/v1/quota", {"Authorization": "Bearer " + KEY}, b"")[0] == 200
    assert not state.jobs


@pytest.mark.parametrize("case", ["api-redirect", "audio-redirect", "malformed", "deadline"])
def test_negative_mock_cases(case):
    state = State(KEY)
    state.configure(case, 200 if case == "deadline" else 0)
    status, headers, job = create(state)
    if case == "api-redirect":
        assert status == 302 and "Location" in headers and not state.jobs
    elif case == "deadline":
        assert job["status"] == "queued"
    else:
        status, headers, body = state.handle("GET", "static.flowspeech.io", "/audio/fixture.wav", {}, b"")
        assert status == (302 if case == "audio-redirect" else 200)
        if case == "audio-redirect":
            assert headers["Location"] == "https://forbidden:fixture@flowspeech.io/redirect-target"
        if case == "malformed":
            assert not body.startswith(b"RIFF")


@pytest.mark.parametrize("case", ["api-redirect", "audio-redirect", "audio-redirect-safe"])
def test_redirect_fixture_matches_unchanged_adapter_contract(case):
    now = [0.0]
    state = State(KEY, clock=lambda: now[0])
    state.configure(case, 1)

    def handle(request):
        status, headers, body = state.handle(request.method, request.url.host, request.url.path,
                                            dict(request.headers), request.content)
        return httpx.Response(status, headers=headers, **({"content": body} if isinstance(body, bytes) else {"json": body}))

    transport = httpx.MockTransport(handle)
    with httpx.Client(transport=transport) as api, httpx.Client(
            transport=transport, follow_redirects=True, auth=("ignored", "ignored"),
            headers={"Authorization": "ignored"}, cookies={"session": "ignored"}) as download:
        client = V1Client(api_key=KEY, http_client=api, download_client=download,
                          clock=lambda: now[0], sleep=lambda delay: now.__setitem__(0, now[0] + delay))
        if case == "audio-redirect-safe":
            job, audio, request_id = client.generate(make_input("CE fixture " + case), request_id=REQUEST_ID)
            assert audio == fixture_wav() and request_id == REQUEST_ID and job["id"] in state.jobs
        else:
            with pytest.raises(ApiError) as caught:
                client.generate(make_input("CE fixture " + case), request_id=REQUEST_ID)
            assert caught.value.request_id == REQUEST_ID
            if case == "audio-redirect":
                assert caught.value.code == "download_failed" and caught.value.job_id in state.jobs
            else:
                assert caught.value.code == "redirect_refused" and not state.jobs
    assert len([c for c in state.calls if c["method"] == "POST"]) == 1
    assert all(c["path"] != "/redirect-target" for c in state.calls)
    downloads = [c for c in state.calls if c["path"].startswith("/audio/")]
    assert len(downloads) == {"api-redirect": 0, "audio-redirect": 1, "audio-redirect-safe": 2}[case]
    assert all(not c["authorization_present"] and not c["cookie_present"] for c in downloads)
    if case == "audio-redirect-safe":
        assert [c["host"] for c in downloads] == ["static.flowspeech.io", "flowspeech.io"]


@pytest.mark.parametrize("headers", [{"Authorization": "Bearer " + KEY}, {"Cookie": "session=fixture"}])
def test_mock_redirect_destination_rejects_credentials(headers):
    state = State(KEY)
    state.configure("audio-redirect-safe", 1)
    assert state.handle("GET", "flowspeech.io", "/audio/redirected.wav", headers, b"")[0] == 403


@pytest.mark.parametrize("defect", [None, "forbidden", "authorization", "cookie", "extra-hop", "persisted-audio"])
def test_deployed_case_keeps_redirect_credentials_and_persistence_assertions(monkeypatch, defect):
    job_id = "22222222-2222-4222-8222-222222222222"

    class WorkflowConsole:
        fixture = {"api_key": KEY}

        def __init__(self):
            self.opener = self

        def json(self, path, **kwargs):
            if path == "/apps":
                return {"id": job_id}
            self.request_id = kwargs["body"]["graph"]["nodes"][1]["data"]["tool_configurations"]["request_id"]
            return {}

        def control(self, path, payload=None):
            if path == "/configure":
                assert payload["case"] == "audio-redirect-safe"
                return {}
            calls = [
                {"host": "flowspeech.io", "path": "/api/v1/tts/jobs", "method": "POST", "elapsed": 0,
                 "request_id": self.request_id, "authorization_present": True, "cookie_present": False},
                {"host": "flowspeech.io", "path": "/api/v1/tts/jobs/" + job_id, "method": "GET", "elapsed": 5},
                {"host": "static.flowspeech.io", "path": "/audio/" + job_id + ".wav", "method": "GET",
                 "authorization_present": False, "cookie_present": False},
                {"host": "flowspeech.io", "path": "/audio/redirected.wav", "method": "GET",
                 "authorization_present": defect == "authorization", "cookie_present": defect == "cookie"}]
            if defect == "forbidden":
                calls.append({"host": "flowspeech.io", "path": "/redirect-target", "method": "GET"})
            if defect == "extra-hop":
                calls.append(dict(calls[-1]))
            return {"calls": calls, "jobs": {job_id: {"id": job_id}}}

        def open(self, path, **kwargs):
            if path.startswith(driver.BASE + "/files/"):
                return io.BytesIO(b"wrong persisted bytes" if defect == "persisted-audio" else fixture_wav())
            outputs = {"audio": [{"url": "/files/tools/fixture.wav"}],
                       "metadata": [{"requestId": self.request_id, "jobId": job_id}]}
            event = {"event": "workflow_finished", "data": {"status": "succeeded", "outputs": outputs}}
            return io.BytesIO(("data: " + json.dumps(event) + "\n").encode())

    clock = iter([0, 5])
    monkeypatch.setattr(driver.time, "monotonic", lambda: next(clock))
    console = WorkflowConsole()
    if defect:
        with pytest.raises(AssertionError):
            driver.run_case(console, "audio-redirect-safe", delay=1, timeout=300, expect_audio=True, minimum=4.8, maximum=60)
        assert console.current_audit is not None
    else:
        result = driver.run_case(console, "audio-redirect-safe", delay=1, timeout=300, expect_audio=True, minimum=4.8, maximum=60)
        assert result["downloads"] == 2 and result["creates"] == 1 and result["audio_files"] == 1
        assert result["persisted_audio_sha256"] == hashlib.sha256(fixture_wav()).hexdigest()


@pytest.mark.parametrize("url", ["https://flowspeech.io/files/a", "http://evil.test/files/a",
                                  "http://user@api:5001/files/a", "http://api:5001/console/api/setup", "//evil.test/a"])
def test_driver_refuses_nonlocal_file_downloads(url):
    with pytest.raises(ValueError):
        file_url(url)


def test_driver_allows_only_ce_file_service():
    assert file_url("/files/tools/a.wav?sign=fixture") == "http://api:5001/files/tools/a.wav?sign=fixture"


def test_real_workflow_has_no_model_or_code_nodes():
    payload = graph("basic", REQUEST_ID, 300)
    assert [node["data"]["type"] for node in payload["nodes"]] == ["start", "tool", "end"]
    tool = payload["nodes"][1]["data"]
    assert tool["provider_id"] == "flowspeech/flowspeech/flowspeech"
    assert tool["tool_name"] == "flowspeech_text_to_speech"
    assert tool["tool_configurations"]["request_id"] == str(uuid.UUID(REQUEST_ID))
    assert len(payload["edges"]) == 2


@pytest.mark.parametrize("lines", [[], [b'data: {"event":"error"}\n'],
                                   [b'data: {"event":"workflow_finished","data":{"status":"failed"}}\n']])
def test_partial_or_failed_workflow_cannot_pass(lines):
    with pytest.raises(AssertionError):
        terminal_event(lines)


def test_sse_terminal_and_heartbeat():
    assert terminal_event([b": ping\n", b'data: {"event":"workflow_finished","data":{"status":"succeeded","outputs":{}}}\n'])["outputs"] == {}


class ProviderConsole:
    """Pinned CE contract: installed tools exist before saved provider credentials."""

    def __init__(self, *, saved=False, invalid_status=401):
        self.fixture = {"api_key": KEY}
        self.saved = saved
        self.invalid_status = invalid_status
        self.events = []
        self.tools = [{"name": "flowspeech_text_to_speech"}]

    def login(self):
        self.events.append("login")

    def json(self, path, **kwargs):
        assert path.startswith(driver.PROVIDER_PATH)
        suffix = path.removeprefix(driver.PROVIDER_PATH)
        self.events.append(suffix)
        if suffix == "/tools":
            return self.tools
        if suffix == "/info":
            if not self.saved:
                raise HTTPError(driver.BASE + "/console/api" + path, 400,
                                "you have not added provider " + driver.PROVIDER, {}, None)
            return {"plugin_id": "flowspeech/flowspeech", "name": "flowspeech"}
        assert suffix == "/add" and kwargs["method"] == "POST"
        if kwargs["body"]["credentials"]["api_key"] != KEY:
            if self.invalid_status != 200:
                raise HTTPError(driver.BASE + "/console/api" + path, self.invalid_status, "Rejected fixture", {}, None)
        self.saved = True
        return {"result": "success"}

    def control(self, path, payload=None):
        self.events.append(path)
        if path == "/audit":
            return {"calls": [{"method": "GET", "path": "/api/v1/quota"}]}
        assert path == "/configure" and payload == {"case": "basic", "delay": 1}
        return {}


@pytest.mark.parametrize("invalid_status", [400, 401, 403])
def test_driver_waits_for_installed_tools_then_saves_credentials_before_info(monkeypatch, invalid_status):
    console = ProviderConsole(invalid_status=invalid_status)
    calls = []

    def run_case(client, case, **kwargs):
        assert client is console and console.saved
        assert console.events == ["login", "/tools", "/configure", "/add", "/audit", "/add", "/info", "/tools"]
        calls.append((case, kwargs))
        return {"case": case}

    monkeypatch.setenv("GATE_HOST_TIMEOUT", "300")
    monkeypatch.setattr(driver, "run_case", run_case)
    progress = []
    assert driver.run(console, progress=progress) is progress
    assert progress[0] == {"case": "provider-credentials", "invalid_rejected": True, "valid_saved": True}
    assert [case for case, _ in calls] == ["basic", "slow", "malformed", "api-redirect", "audio-redirect", "audio-redirect-safe", "deadline"]
    assert calls[1][1] == {"delay": 200, "timeout": 300, "expect_audio": True, "minimum": 199, "maximum": 295}
    assert calls[-1][1] == {"delay": 200, "timeout": 10, "expect_audio": False, "minimum": 4, "maximum": 15}


def test_driver_still_rejects_a_host_that_accepts_invalid_credentials(monkeypatch):
    console = ProviderConsole(invalid_status=200)
    monkeypatch.setenv("GATE_HOST_TIMEOUT", "300")
    with pytest.raises(AssertionError, match="CE accepted invalid"):
        driver.run(console)
    assert console.current_case == "provider-invalid-credentials"
    assert "/info" not in console.events


def test_driver_requires_exact_tool_name_not_a_string_match(monkeypatch):
    console = ProviderConsole()
    console.tools = [{"name": "wrong_tool", "description": "flowspeech_text_to_speech"}]
    monkeypatch.setenv("GATE_HOST_TIMEOUT", "300")
    with pytest.raises(AssertionError):
        driver.run(console)
    assert console.current_case == "provider-readiness"
    assert console.events == ["login", "/tools"]


@pytest.mark.parametrize("saved", [True, False])
def test_short_host_requires_existing_saved_credentials_without_adding_again(monkeypatch, saved):
    console = ProviderConsole(saved=saved)
    calls = []
    monkeypatch.setenv("GATE_HOST_TIMEOUT", "180")
    monkeypatch.setattr(driver, "run_case", lambda client, case, **kwargs: calls.append((case, kwargs)) or {"case": case})
    if saved:
        assert driver.run(console, short_host=True) == [{"case": "deadline"}]
        assert calls == [("deadline", {"delay": 200, "timeout": 300, "expect_audio": False, "minimum": 160, "maximum": 180})]
    else:
        with pytest.raises(HTTPError) as caught:
            driver.run(console, short_host=True)
        assert caught.value.code == 400 and not calls
        assert console.current_case == "provider-saved-credentials"
    assert console.events == ["login", "/tools", "/info"]


@pytest.mark.parametrize("status", [301, 302, 400, 401, 403, 404, 422])
def test_readiness_does_not_hide_permanent_http_errors(monkeypatch, status):
    error = HTTPError(driver.BASE + "/console/api" + driver.PROVIDER_PATH + "/info", status, "Fixture rejection", {}, None)
    calls = []

    def check():
        calls.append("request")
        raise error

    monkeypatch.setattr(driver.time, "sleep", lambda _: pytest.fail("Permanent failures must not be retried"))
    with pytest.raises(HTTPError) as caught:
        driver.wait_for(check, 120)
    assert caught.value is error and calls == ["request"]


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_readiness_still_retries_transient_http_errors(monkeypatch, status):
    calls = []
    waits = []

    def check():
        calls.append("request")
        if len(calls) == 1:
            raise HTTPError(driver.BASE + "/console/api/setup", status, "Fixture startup", {}, None)
        return {"step": "not_started"}

    monkeypatch.setattr(driver.time, "monotonic", lambda: 0)
    monkeypatch.setattr(driver.time, "sleep", waits.append)
    assert driver.wait_for(check, 120) == {"step": "not_started"}
    assert len(calls) == 2 and waits == [3]


def test_readiness_transient_failure_still_hits_deadline(monkeypatch):
    now = [0]
    calls = []

    def check():
        calls.append("request")
        raise HTTPError(driver.BASE + "/console/api/setup", 503, "Fixture startup", {}, None)

    monkeypatch.setattr(driver.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(driver.time, "sleep", lambda duration: now.__setitem__(0, now[0] + duration))
    with pytest.raises(TimeoutError, match="readiness/install deadline exceeded"):
        driver.wait_for(check, 3)
    assert now == [3] and len(calls) == 2


def test_compose_fails_closed_and_pins_every_image():
    compose = yaml.safe_load((GATE / "compose.yaml").read_text())
    pins = json.loads((GATE / "pins.json").read_text())
    assert compose["networks"] == {"gate": {"internal": True}}
    for service in compose["services"].values():
        assert service["image"] in pins["images"].values()
        assert "@sha256:" in service["image"]
        assert not service.get("ports") and not service.get("privileged")
        assert service.get("network_mode") == "none" or set(service["networks"]) == {"gate"}
    daemon = compose["services"]["plugin_daemon"]["environment"]
    assert "--no-index" in daemon["PIP_EXTRA_ARGS"]
    assert daemon["PIP_MIRROR_AUTO_DETECT"] == "false"
    assert compose["services"]["mock"]["networks"]["gate"]["aliases"] == ["flowspeech.io", "static.flowspeech.io"]


def inspected_container(mode="ce_gate"):
    return {"Config": {"Labels": {"com.docker.compose.service": "init-storage" if mode == "none" else "api"},
                       "Env": ["SECRET=never-upload-inspect-env"]},
            "HostConfig": {"Privileged": False, "PortBindings": {}, "NetworkMode": mode},
            "NetworkSettings": {"Networks": {mode: {"NetworkID": "network-id", "EndpointID": "endpoint-id",
                                                     "IPAddress": "", "Gateway": "", "IPPrefixLen": 0,
                                                     "GlobalIPv6Address": "", "IPv6Gateway": ""}}},
            "Mounts": [], "Image": "sha256:fixture-image"}


@pytest.mark.parametrize("attached", [{}, {"none": {"NetworkID": "none-id", "EndpointID": "endpoint-id",
                                                   "IPAddress": "", "Gateway": ""}}])
def test_isolation_allows_network_disabled_init_container(attached):
    container = inspected_container("none")
    container["NetworkSettings"]["Networks"] = attached
    check_isolation.validate_container(container, {"ce_gate"})


def test_isolation_allows_only_internal_network_for_running_service():
    container = inspected_container()
    container["NetworkSettings"]["Networks"]["ce_gate"].update(IPAddress="172.18.0.3", Gateway="172.18.0.1")
    check_isolation.validate_container(container, {"ce_gate"})


@pytest.mark.parametrize("mode", ["host", "bridge", "default", "container:other-id", "external"])
def test_isolation_rejects_other_network_modes_even_with_internal_attachment(mode):
    container = inspected_container()
    container["HostConfig"]["NetworkMode"] = mode
    with pytest.raises(RuntimeError, match="api: container must use only"):
        check_isolation.validate_container(container, {"ce_gate"})


@pytest.mark.parametrize("mode", ["none", "ce_gate"])
def test_isolation_rejects_extra_network_attachment(mode):
    container = inspected_container(mode)
    container["NetworkSettings"]["Networks"]["external"] = {}
    with pytest.raises(RuntimeError, match="another network attached|must use only"):
        check_isolation.validate_container(container, {"ce_gate"})


def test_isolation_rejects_networked_service_without_its_internal_attachment():
    container = inspected_container()
    container["NetworkSettings"]["Networks"] = {}
    with pytest.raises(RuntimeError, match="must use only"):
        check_isolation.validate_container(container, {"ce_gate"})


@pytest.mark.parametrize("field,value", [("IPAddress", "172.18.0.3"), ("Gateway", "172.18.0.1"),
                                        ("GlobalIPv6Address", "fd00::3"), ("IPv6Gateway", "fd00::1"),
                                        ("IPPrefixLen", 16), ("GlobalIPv6PrefixLen", 64)])
@pytest.mark.parametrize("location", ["top-level", "endpoint"])
def test_isolation_rejects_addresses_or_routes_in_none_mode(field, value, location):
    container = inspected_container("none")
    settings = container["NetworkSettings"]
    target = settings if location == "top-level" else settings["Networks"]["none"]
    target[field] = value
    with pytest.raises(RuntimeError, match="init-storage: .*IP address or route"):
        check_isolation.validate_container(container, {"ce_gate"})


@pytest.mark.parametrize("unsafe", ["privileged", "published-port", "docker-socket"])
@pytest.mark.parametrize("mode", ["none", "ce_gate"])
def test_isolation_never_exempts_none_mode_from_host_protections(unsafe, mode):
    container = inspected_container(mode)
    if unsafe == "privileged":
        container["HostConfig"]["Privileged"] = True
    elif unsafe == "published-port":
        container["HostConfig"]["PortBindings"] = {"5001/tcp": [{"HostIp": "", "HostPort": "5001"}]}
    else:
        container["Mounts"] = [{"Destination": "/var/run/docker.sock"}]
    with pytest.raises(RuntimeError, match="privileged container|Docker socket"):
        check_isolation.validate_container(container, {"ce_gate"})


@pytest.mark.parametrize("failure", [None, "external-attachment", "external-network", "empty-containers", "empty-wheels"])
def test_isolation_inspection_retains_safe_evidence_on_success_and_failure(tmp_path, monkeypatch, failure):
    containers = [inspected_container(), inspected_container("none")]
    networks = [{"Name": "ce_gate", "Internal": failure != "external-network"}]
    if failure == "external-attachment":
        containers[1]["NetworkSettings"]["Networks"]["bridge"] = {}
    if failure == "empty-containers":
        containers = []
    if failure != "empty-wheels":
        (tmp_path / "wheels").mkdir()
        (tmp_path / "wheels/fixture.whl").write_bytes(b"fixture wheel")
    monkeypatch.setenv("GATE_STATE", str(tmp_path))
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "ce")

    def docker(*args):
        if args[:2] == ("network", "ls"):
            return "network-id\n"
        if args[:2] == ("network", "inspect"):
            return json.dumps(networks)
        if args[:2] == ("ps", "-aq"):
            return "api-id\ninit-id\n" if containers else ""
        assert args == ("inspect", "api-id", "init-id")
        return json.dumps(containers)

    monkeypatch.setattr(check_isolation, "docker", docker)
    if failure:
        with pytest.raises(RuntimeError):
            check_isolation.main()
    else:
        check_isolation.main()
    text = (tmp_path / "evidence/isolation.json").read_text()
    evidence = json.loads(text)
    assert "never-upload-inspect-env" not in text and '"Env"' not in text
    assert evidence["status"] == ("failed" if failure else "passed")
    if failure == "external-attachment":
        assert evidence["error"].startswith("init-storage:")
        assert evidence["containers"][1]["attached_networks"] == ["bridge", "none"]
    if not failure:
        assert evidence["all_networks_internal"] and evidence["no_published_ports"]
        assert evidence["containers"][1]["network_mode"] == "none"
        assert evidence["dependency_wheel_sha256"] == {"fixture.whl": hashlib.sha256(b"fixture wheel").hexdigest()}


@pytest.mark.parametrize("isolation_status", [None, "failed", "passed"])
def test_summary_requires_passed_isolation_as_well_as_workflows(tmp_path, monkeypatch, isolation_status):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    for stage in ("install", "run", "short-host"):
        (evidence / (stage + ".json")).write_text(json.dumps({"status": "passed"}))
    if isolation_status:
        (evidence / "isolation.json").write_text(json.dumps({"status": isolation_status}))
    monkeypatch.setenv("GATE_STATE", str(tmp_path))
    monkeypatch.setattr(collect.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "", ""))
    collect.main()
    summary = json.loads((evidence / "summary.json").read_text())
    assert summary["ce_passed"] is (isolation_status == "passed")
    assert summary["stages"]["isolation"] == (isolation_status or "not_run")
    assert summary["cloud_passed"] is False


def test_workflow_has_bounded_read_only_permissions_and_no_secret_upload():
    # BaseLoader preserves YAML's 'on' key instead of YAML 1.1 boolean coercion.
    workflow = yaml.load((ROOT / ".github/workflows/deployed-ce.yml").read_text(), Loader=yaml.BaseLoader)
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["deployed-ce"]["timeout-minutes"] == "40"
    steps = workflow["jobs"]["deployed-ce"]["steps"]
    upload = next(step for step in steps if "upload-artifact@" in step.get("uses", ""))
    assert upload["with"]["path"].endswith("/evidence/")
    assert "steps.evidence.outcome == 'success'" in upload["if"]
    assert not any("secrets." in json.dumps(step) for step in steps)


def test_state_path_is_initialized_at_step_runtime(tmp_path):
    workflow = yaml.load((ROOT / ".github/workflows/deployed-ce.yml").read_text(), Loader=yaml.BaseLoader)
    job = workflow["jobs"]["deployed-ce"]
    assert "GATE_STATE" not in job["env"]
    assert "runner." not in json.dumps(job["env"])
    initialize = job["steps"][0]
    env_file = tmp_path / "github-env"
    runner_temp = tmp_path / "runner temp with spaces"
    subprocess.run(["bash", "-eu", "-c", initialize["run"]], check=True,
                   env={"RUNNER_TEMP": str(runner_temp), "GITHUB_ENV": str(env_file)})
    assert env_file.read_text() == f"GATE_STATE={runner_temp}/flowspeech-ce-gate\n"
    assert "actions/checkout@" in job["steps"][1]["uses"]


def test_log_redaction_does_not_retain_generated_auth():
    secret = "never-retain-this-fixture-value"
    text = "Authorization: Bearer " + secret + "\nCookie: test=private\n" + secret
    result = redact(text, [secret])
    assert secret not in result and "test=private" not in result


def test_reviewed_package_hash_is_pinned():
    pins = json.loads((GATE / "pins.json").read_text())
    package = ROOT / "dist/flowspeech-0.2.0.difypkg"
    if package.exists():
        assert hashlib.sha256(package.read_bytes()).hexdigest() == pins["package_sha256"]
    assert "/45c04d1b0ad75206ac5c3efb9cfc7f5685d845ac/" in pins["package_url"]
