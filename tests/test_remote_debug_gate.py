"""Offline contract/security tests for the separate real remote-protocol CI gate."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
import zipfile

import pytest
import yaml

from scripts.remote_debug import collect, driver, isolation, prepare, runtime
from scripts.deployed_ce import prepare as ce_prepare

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/remote_debug"
KEY = "12345678-1234-4234-8234-123456789abc"
APP = "22345678-1234-4234-8234-123456789abc"
IDENTITY = "flowspeech/flowspeech:0.2.0@" + "a" * 64
MISSING = "plugin provider flowspeech/flowspeech/flowspeech not found"


class Console:
    def __init__(self):
        self.fixture = {"api_key": "isolated-fixture-key", "email": "test@example.com", "password": "fixture-password"}
        self.items = []
        self.events = []
        self.key_response = {"key": KEY, "host": "plugin_daemon", "port": 5003}
        self.setup = "not_started"
        self.audit = {"calls": [], "jobs": {}}
        self.stream = [sse({"event": "workflow_finished", "data": {"status": "failed", "error": MISSING}})]
        self.saved = {"result": "success"}

    def login(self):
        self.events.append(("login", {}))

    def json(self, path, **kwargs):
        self.events.append((path, kwargs))
        if path == "/setup":
            return {"step": self.setup}
        if path == driver.LIST:
            return {"plugins": self.items}
        if path == driver.DEBUG_KEY:
            return self.key_response
        if path.endswith("/add"):
            self.audit["calls"] = [{"host": "flowspeech.io", "path": "/api/v1/quota", "method": "GET",
                                     "authorization_present": True, "cookie_present": False}]
            return self.saved
        if path.endswith("/info"):
            return {}
        if path.endswith("/tools"):
            return [{"name": "flowspeech_text_to_speech"}]
        raise AssertionError(path)

    def control(self, path, payload=None):
        self.events.append((path, payload))
        return self.audit

    def open(self, path, **kwargs):
        self.events.append((path, kwargs))
        if isinstance(self.stream, Exception):
            raise self.stream
        return io.BytesIO(b"".join(self.stream))


def sse(event):
    return ("data: " + json.dumps(event) + "\n\n").encode()


def remote_item(**changes):
    return {"plugin_unique_identifier": IDENTITY, "runtime_type": "remote", **changes}


def test_prepare_uses_pinned_package_fresh_state_and_explicit_debug_limits(tmp_path, monkeypatch):
    # Ordinary test CI has no ignored dist/ artifact; use a synthetic archive and a fixture-only pin.
    package = tmp_path / "candidate.difypkg"
    names = ["main.py", "runtime_config.py", "flowspeech_v1.py"] + [f"unit{i}.py" for i in range(5)]
    with zipfile.ZipFile(package, "w") as archive:
        for name in names:
            archive.writestr(name, b"fixture Python source")
        archive.writestr("manifest.yaml", b"version: 0.2.0\n")
        for i in range(8):
            archive.writestr(f"fixture{i}.txt", b"fixture member")
    pins = {"package_sha256": hashlib.sha256(package.read_bytes()).hexdigest()}
    reference = tmp_path / "reference"
    reference.mkdir()
    (reference / "pins.json").write_text(json.dumps(pins))
    monkeypatch.setattr(ce_prepare, "ROOT", reference)
    prepare.prepare(tmp_path)
    settings = dict(line.split("=", 1) for line in (tmp_path / "runtime.env").read_text().splitlines())
    assert settings["PLUGIN_REMOTE_INSTALLING_ENABLED"] == "true"
    assert settings["PLUGIN_REMOTE_INSTALLING_HOST"] == "0.0.0.0"
    assert settings["PLUGIN_REMOTE_INSTALLING_PORT"] == settings["PLUGIN_REMOTE_INSTALL_PORT"] == "5003"
    assert settings["PLUGIN_REMOTE_INSTALL_HOST"] == "plugin_daemon"
    # The pinned daemon rejects every completed handshake if maxConn remains zero.
    assert settings["PLUGIN_REMOTE_INSTALLING_MAX_CONN"] == "2"
    assert settings["PLUGIN_REMOTE_INSTALL_SERVER_EVENT_LOOP_NUMS"] == "1"
    assert (tmp_path / "remote-key").read_text() == ""
    assert (tmp_path / "remote-key").stat().st_mode & 0o777 == 0o600
    report = runtime.identity(tmp_path / "candidate.difypkg", tmp_path / "plugin", pins["package_sha256"])
    assert report["python_files_matched"] == 8 and report["all_members_matched"] == 17
    with pytest.raises(ValueError, match="fresh"):
        prepare.prepare(tmp_path)


def test_prepare_rejects_unreviewed_package(tmp_path):
    (tmp_path / "candidate.difypkg").write_bytes(b"not the reviewed package")
    with pytest.raises(ValueError, match="reviewed"):
        prepare.prepare(tmp_path)
    assert not (tmp_path / "runtime.env").exists()


@pytest.mark.parametrize("defect", [None, "python", "manifest", "extra", "missing", "symlink", "hash", "count"])
def test_runtime_identity_matches_all_members_and_exactly_eight_python_files(tmp_path, defect):
    package = tmp_path / "candidate.difypkg"
    root = tmp_path / "plugin"
    root.mkdir()
    names = [f"source{i}.py" for i in range(8)] + ["manifest.yaml"]
    with zipfile.ZipFile(package, "w") as archive:
        for name in names[:-1] if defect == "count" else names:
            archive.writestr(name, b"reviewed content")
        if defect == "count":
            archive.writestr("source8.py", b"extra source")
    with zipfile.ZipFile(package) as archive:
        archive.extractall(root)
    sha = hashlib.sha256(package.read_bytes()).hexdigest()
    if defect in {"python", "manifest"}:
        (root / ("source0.py" if defect == "python" else "manifest.yaml")).write_text("changed")
    elif defect == "extra":
        (root / "injected.py").write_text("extra")
    elif defect == "missing":
        (root / "source0.py").unlink()
    elif defect == "symlink":
        (root / "source0.py").unlink()
        (root / "source0.py").symlink_to(root / "source1.py")
    elif defect == "hash":
        sha = "0" * 64
    if defect:
        with pytest.raises(AssertionError):
            runtime.identity(package, root, sha)
    else:
        assert runtime.identity(package, root, sha)["python_files_matched"] == 8


def test_ca_only_changes_disposable_venv_bundle_and_is_idempotent(tmp_path):
    venv = tmp_path / "venv"
    bundle = venv / "lib/python3.12/site-packages/certifi/cacert.pem"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"original trusted roots")
    ca = tmp_path / "ca.crt"
    ca.write_bytes(b"-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----\n")
    for _ in range(2):
        assert runtime.trust_ca(venv, ca) == hashlib.sha256(ca.read_bytes()).hexdigest()
    assert bundle.read_bytes() == b"original trusted roots\n" + ca.read_bytes()


def test_launch_env_cannot_inherit_host_secrets_or_pythonpath(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/production/source")
    monkeypatch.setenv("FLOWSPEECH_API_KEY", "do-not-inherit")
    env = runtime.launch_environment(KEY)
    assert env["INSTALL_METHOD"] == "remote" and env["REMOTE_INSTALL_URL"] == "plugin_daemon:5003"
    assert env["REMOTE_INSTALL_KEY"] == KEY and env["MAX_REQUEST_TIMEOUT"] == "300"
    assert not {"PYTHONPATH", "FLOWSPEECH_API_KEY"} & env.keys()
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"


@pytest.mark.parametrize("key", ["", "not-a-uuid", KEY + "\nINJECT=value"])
def test_launch_rejects_malformed_key(key):
    with pytest.raises((AssertionError, ValueError)):
        runtime.launch_environment(key)


def test_launch_executes_original_entrypoint_without_importing_or_patching_plugin(monkeypatch):
    files = {
        "/scripts/deployed_ce/pins.json": json.dumps({"package_sha256": "expected-sha"}),
        "/remote-key": KEY,
    }
    writes = {}
    monkeypatch.setattr(runtime.Path, "read_text", lambda self: files[str(self)])
    monkeypatch.setattr(runtime.Path, "write_text", lambda self, text: writes.__setitem__(str(self), text))
    monkeypatch.setattr(runtime, "identity", lambda package, root, expected: {"python_files_matched": 8})
    monkeypatch.setattr(runtime, "trust_ca", lambda venv, ca: "fixture-ca-sha")
    monkeypatch.setattr(runtime.sys, "argv", ["runtime", "launch"])
    calls = []
    monkeypatch.setattr(runtime.os, "chdir", lambda path: calls.append(("cwd", path)))
    monkeypatch.setattr(runtime.os, "execve", lambda exe, args, env: calls.append((exe, args, env)))
    runtime.main()
    assert calls[0] == ("cwd", "/plugin")
    assert calls[1][0:2] == ("/runtime/venv/bin/python", ["/runtime/venv/bin/python", "-m", "main"])
    assert calls[1][2]["INSTALL_METHOD"] == "remote"
    assert KEY not in json.dumps(writes)
    report = json.loads(writes["/evidence/runtime-identity.json"])
    assert report["entrypoint"] == "python -m main" and report["python_files_matched"] == 8


def test_bootstrap_uses_official_console_api_without_package_install(tmp_path):
    console = Console()
    result = driver.bootstrap(console, tmp_path)
    assert result["initial_plugins"] == 0 and result["local_install_calls"] == 0
    assert (tmp_path / "remote-key").read_text() == KEY
    assert (tmp_path / "remote-key").stat().st_mode & 0o777 == 0o600
    assert KEY in collect.secrets(tmp_path)
    assert KEY not in json.dumps(result)
    assert [path for path, _ in console.events] == ["/setup", "/setup", "login", driver.LIST, driver.DEBUG_KEY]


@pytest.mark.parametrize("defect", ["not-fresh", "installed", "host", "port", "key"])
def test_bootstrap_fails_closed_and_remembers_debug_key_for_redaction(tmp_path, defect):
    console = Console()
    if defect == "not-fresh":
        console.setup = "finished"
    elif defect == "installed":
        console.items = [remote_item()]
    else:
        console.key_response[{"host": "host", "port": "port", "key": "key"}[defect]] = {
            "host": "outside.example", "port": 443, "key": "bad-key-format"}[defect]
    with pytest.raises((AssertionError, ValueError)):
        driver.bootstrap(console, tmp_path)
    assert not (tmp_path / "remote-key").exists()
    if defect in {"host", "port", "key"}:
        assert console.key_response["key"] in collect.secrets(tmp_path)


@pytest.mark.parametrize("items", [
    [remote_item(runtime_type="local")], [remote_item(runtime_type="serverless")],
    [remote_item(plugin_unique_identifier="other/tool:0.2.0@" + "a" * 64)],
    [remote_item(plugin_unique_identifier=IDENTITY + "suffix")], [remote_item(), remote_item()],
])
def test_registration_never_accepts_local_duplicate_or_other_plugin(items):
    console = Console()
    console.items = items
    with pytest.raises(AssertionError):
        driver.entries(console)


def test_connected_requires_remote_dispatch_then_saved_credentials_and_persisted_workflow(tmp_path, monkeypatch):
    console = Console()
    console.items = [remote_item()]
    calls = []

    def ready(client, seconds):
        calls.append("invalid-quota")
        assert client is console and seconds == 90
        return {"invalid_rejected": True}

    def basic(client, case, **kwargs):
        calls.append("basic")
        assert any(path.endswith("/info") for path, _ in console.events)
        assert case == "basic" and kwargs == {"delay": 1, "timeout": 300, "expect_audio": True, "minimum": 4.8, "maximum": 60}
        client.last_app_id = APP
        return {"persisted_audio_sha256": "fixture-sha", "creates": 1}

    monkeypatch.setattr(driver.ce, "wait_for_runtime", ready)
    monkeypatch.setattr(driver.ce, "run_case", basic)
    report = driver.connected(console, tmp_path)
    assert calls == ["invalid-quota", "basic"]
    assert report["runtime_type"] == "remote" and report["valid_credentials_saved"]
    assert json.loads((tmp_path / "dispatch.json").read_text()) == {"app_id": APP, "identity": IDENTITY}


@pytest.mark.parametrize("defect", ["save-rejected", "job", "create", "cookie", "no-auth", "wrong-host", "no-calls"])
def test_connected_never_runs_workflow_without_quota_only_credential_save(tmp_path, monkeypatch, defect):
    console = Console()
    console.items = [remote_item()]
    original = console.json

    def request(path, **kwargs):
        value = original(path, **kwargs)
        if path.endswith("/add"):
            if defect == "save-rejected":
                return {"result": "failed"}
            if defect == "job":
                console.audit["jobs"] = {APP: {}}
            elif defect == "no-calls":
                console.audit["calls"] = []
            else:
                key, val = {"create": ("method", "POST"), "cookie": ("cookie_present", True),
                            "no-auth": ("authorization_present", False), "wrong-host": ("host", "storage")}.get(defect, ("path", "/api/v1/quota"))
                console.audit["calls"][0][key] = val
        return value

    console.json = request
    monkeypatch.setattr(driver.ce, "wait_for_runtime", lambda *a: {})
    monkeypatch.setattr(driver.ce, "run_case", lambda *a, **kw: pytest.fail("Must not invoke"))
    with pytest.raises(AssertionError):
        driver.connected(console, tmp_path)


@pytest.mark.parametrize("event", [
    {"event": "workflow_finished", "data": {"status": "succeeded", "outputs": {}}},
    {"event": "workflow_finished", "data": {"status": "failed", "error": "Invalid credentials"}},
    {"event": "workflow_finished", "data": {"status": "failed", "error": MISSING, "outputs": {"audio": ["file"]}}},
    {"event": "error", "message": "certificate verify failed"},
    {"event": "error", "message": "Unauthorized"},
    {"event": "workflow_started"},
])
def test_disconnect_rejects_success_unrelated_error_audio_or_no_terminal(event):
    with pytest.raises(AssertionError):
        driver.failed_dispatch([sse(event)])


@pytest.mark.parametrize("message", [MISSING, "PluginDaemonInternalServerError: no available node, plugin runtime not found"])
@pytest.mark.parametrize("kind", ["workflow_finished", "error"])
def test_disconnect_requires_explicit_unavailable_runtime(message, kind):
    event = {"event": kind, "message": message, "data": {"status": "failed", "error": message}}
    assert driver.failed_dispatch([b": ping\n", sse(event)]) == message


@pytest.mark.parametrize("transport", ["sse", "http400", "http404"])
def test_disconnected_checks_same_successful_draft_zero_api_calls_and_no_fallback(tmp_path, transport):
    console = Console()
    (tmp_path / "dispatch.json").write_text(json.dumps({"app_id": APP, "identity": IDENTITY}))
    if transport != "sse":
        console.stream = HTTPError("http://api:5001/fixture", int(transport[4:]), "unavailable", {},
                                   io.BytesIO(json.dumps({"message": MISSING}).encode()))
    report = driver.disconnected(console, tmp_path)
    assert report["same_workflow_dispatch_failed"] and report["creates"] == 0
    assert [path for path, _ in console.events if "/workflows/" in path] == [f"/apps/{APP}/workflows/draft/run"]
    assert sum(path == driver.LIST for path, _ in console.events) == 2


@pytest.mark.parametrize("defect", ["call", "job", "local", "http-auth", "http-server", "http-other"])
def test_disconnected_cannot_pass_on_live_api_or_fallback_or_unrelated_http(tmp_path, defect):
    console = Console()
    (tmp_path / "dispatch.json").write_text(json.dumps({"app_id": APP}))
    if defect == "call":
        console.audit["calls"] = [{"method": "POST"}]
    elif defect == "job":
        console.audit["jobs"] = {APP: {}}
    elif defect == "local":
        console.items = [remote_item(runtime_type="local")]
    else:
        status = {"http-auth": 401, "http-server": 500, "http-other": 400}[defect]
        console.stream = HTTPError("http://api:5001/fixture", status, "rejected", {}, io.BytesIO(b'{"message":"unrelated"}'))
    with pytest.raises(AssertionError):
        driver.disconnected(console, tmp_path)


def test_console_forbids_local_install_routes_before_any_network_call():
    console = driver.Console({})
    for path in ("/workspaces/current/plugin/upload/pkg", "/workspaces/current/plugin/install/pkg"):
        with pytest.raises(AssertionError, match="forbidden"):
            console.json(path)


def test_compose_pins_and_isolates_all_services_without_daemon_package_or_source_mount():
    compose = yaml.safe_load((GATE / "compose.yaml").read_text())
    pins = json.loads((ROOT / "scripts/deployed_ce/pins.json").read_text())
    assert compose["networks"] == {"gate": {"internal": True}}
    for service in compose["services"].values():
        assert service["image"] in pins["images"].values()
        assert not service.get("ports") and not service.get("privileged")
        assert service.get("network_mode") == "none" or set(service["networks"]) == {"gate"}
        assert "docker.sock" not in json.dumps(service)
    daemon = compose["services"]["plugin_daemon"]
    assert daemon["volumes"] == ["plugin-storage:/app/storage"]
    remote = compose["services"]["remote_plugin"]
    assert remote["restart"] == "no" and remote["command"][-1] == "launch"
    assert "${GATE_STATE:?Set GATE_STATE}/plugin:/plugin:ro" in remote["volumes"]
    assert "${GATE_STATE:?Set GATE_STATE}/remote-key:/remote-key:ro" in remote["volumes"]
    assert compose["services"]["stage-runtime"]["network_mode"] == "none"


@pytest.mark.parametrize("remote_count", [0, 1, 2])
def test_isolation_requires_one_running_remote_process_and_retains_failure(tmp_path, monkeypatch, remote_count):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    monkeypatch.setenv("GATE_STATE", str(tmp_path))
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "flowspeech-remote-1-1")
    monkeypatch.setattr(isolation.sys, "argv", ["isolation", "remote"])
    monkeypatch.setattr(isolation.check_isolation, "main", lambda: (evidence / "isolation.json").write_text('{"status":"passed"}'))
    monkeypatch.setattr(isolation.check_isolation, "docker", lambda *args: "id\n" * remote_count)
    if remote_count == 1:
        isolation.main()
    else:
        with pytest.raises(AssertionError):
            isolation.main()
    assert json.loads((evidence / "isolation-remote.json").read_text())["status"] == ("passed" if remote_count == 1 else "failed")


def test_debug_key_is_redacted_from_logs_and_forbidden_in_json(tmp_path):
    (tmp_path / "fixture.json").write_text(json.dumps({"remote_debug_key": KEY}))
    (tmp_path / "remote-key").write_text(KEY)
    sensitive = collect.secrets(tmp_path)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    logs = collect.redact(f"debug key {KEY}\nCookie: private=value\nAuthorization: Bearer {KEY}", sensitive)
    (evidence / "service-logs.txt").write_text(logs)
    collect.check_evidence(evidence, sensitive)
    assert KEY not in logs and "private=value" not in logs
    (evidence / "bootstrap.json").write_text(json.dumps({"accidental_key": KEY}))
    with pytest.raises(AssertionError, match="credential"):
        collect.check_evidence(evidence, sensitive)


@pytest.mark.parametrize("leaked", [False, True])
def test_finalization_removes_private_state_even_when_upload_is_refused(tmp_path, monkeypatch, leaked):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (tmp_path / "remote-key").write_text(KEY)
    (tmp_path / "fixture.json").write_text(json.dumps({"remote_debug_key": KEY}))
    (tmp_path / "runtime.env").write_text("SERVER_KEY=fixture-server-secret\n")
    (tmp_path / "ca.key").write_text("fixture-private-ca")
    if leaked:
        (evidence / "bootstrap.json").write_text(json.dumps({"key": KEY}))
    monkeypatch.setenv("GATE_STATE", str(tmp_path))
    monkeypatch.setattr(collect.sys, "argv", ["collect", "finalize"])
    if leaked:
        with pytest.raises(AssertionError, match="credential"):
            collect.main()
        assert not (evidence / "summary.json").exists()
    else:
        collect.main()
        summary = json.loads((evidence / "summary.json").read_text())
        assert summary["ephemeral_credential_files_removed"] and not summary["remote_debug_passed"]
    assert all(not (tmp_path / name).exists() for name in collect.PRIVATE_STATE)


@pytest.mark.parametrize("defect", ["file", "directory", "symlink", "certificate", "jwt"])
def test_evidence_allowlist_rejects_unexpected_or_sensitive_material(tmp_path, defect):
    if defect == "file":
        (tmp_path / "remote-key").write_text(KEY)
    elif defect == "directory":
        (tmp_path / "summary.json").mkdir()
    elif defect == "symlink":
        (tmp_path / "summary.json").symlink_to(ROOT / "manifest.yaml")
    elif defect == "certificate":
        (tmp_path / "service-logs.txt").write_text("-----BEGIN PRIVATE KEY-----")
    else:
        (tmp_path / "service-logs.txt").write_text("eyJhbGci.fake.payload")
    with pytest.raises(AssertionError):
        collect.check_evidence(tmp_path, [])


@pytest.mark.parametrize("missing", [None, *collect.STAGES])
def test_summary_requires_all_stages_including_isolation_and_cleanup(tmp_path, missing):
    for stage in collect.STAGES:
        if stage != missing:
            (tmp_path / (stage + ".json")).write_text('{"status":"passed"}')
    summary = collect.summary(tmp_path)
    assert summary["remote_debug_passed"] is (missing is None)
    assert summary["cloud_passed"] is False and "ce_passed" not in summary


@pytest.mark.parametrize("leftover", [None, "containers", "networks", "volumes"])
def test_cleanup_is_scoped_and_verifies_no_resource_leftovers(tmp_path, monkeypatch, leftover):
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "flowspeech-remote-123-1")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["capture_output"] and kwargs["check"]
        resource = "containers" if "ps" in command else "networks" if "network" in command else "volumes" if "volume" in command else None
        return subprocess.CompletedProcess(command, 0, "remaining\n" if resource and resource == leftover else "", "")

    monkeypatch.setattr(collect.subprocess, "run", run)
    if leftover:
        with pytest.raises(AssertionError):
            collect.cleanup(tmp_path)
    else:
        collect.cleanup(tmp_path)
    assert "--remove-orphans" in calls[0]
    assert all("label=com.docker.compose.project=flowspeech-remote-123-1" in call for call in calls[1:])
    report = json.loads((tmp_path / "cleanup.json").read_text())
    assert report["status"] == ("failed" if leftover else "passed")
    assert report["compose_profiles"] == ["validation"]
    assert {name: report[name + "_remaining"] for name in ("containers", "networks", "volumes")} == {
        name: int(name == leftover) for name in ("containers", "networks", "volumes")}


def test_cleanup_removes_explicitly_started_profile_service_not_counted_as_orphan(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "flowspeech-remote-123-1")
    compose = yaml.safe_load((GATE / "compose.yaml").read_text())
    profiled = {name for name, service in compose["services"].items() if service.get("profiles")}
    assert all(compose["services"][name]["profiles"] == ["validation"] for name in profiled)
    # Model the observed lifecycle: explicitly started, then stopped, but still declared.
    remaining = {"api", "remote_plugin"}

    def run(command, **kwargs):
        if "down" in command:
            profiles = {command[i + 1] for i, word in enumerate(command[:-1]) if word == "--profile"}
            remaining.difference_update(name for name, service in compose["services"].items()
                                        if not service.get("profiles") or profiles.intersection(service["profiles"]))
            # --remove-orphans cannot remove declared inactive-profile containers.
            remaining.intersection_update(compose["services"])
            return subprocess.CompletedProcess(command, 0, "", "")
        if "ps" in command:
            output = "\n".join(sorted(remaining))
        elif "network" in command or "volume" in command:
            output = "still-attached-resource" if remaining else ""
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(collect.subprocess, "run", run)
    collect.cleanup(tmp_path)
    assert remaining == set()
    assert json.loads((tmp_path / "cleanup.json").read_text())["status"] == "passed"


def test_logs_include_profiled_remote_client_and_redact_its_generated_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("GATE_STATE", str(tmp_path))
    monkeypatch.setattr(collect.sys, "argv", ["collect", "logs"])
    (tmp_path / "fixture.json").write_text(json.dumps({"remote_debug_key": KEY, "api_key": "fixture-audio-secret"}))

    def run(command, **kwargs):
        assert "logs" in command and command[command.index("--profile") + 1] == "validation"
        return subprocess.CompletedProcess(command, 0, "remote_plugin-1 | key=" + KEY + " credentials=fixture-audio-secret", "")

    monkeypatch.setattr(collect.subprocess, "run", run)
    collect.main()
    retained = (tmp_path / "evidence/service-logs.txt").read_text()
    assert "remote_plugin-1" in retained
    assert KEY not in retained and "fixture-audio-secret" not in retained


@pytest.mark.parametrize("project", ["", "dify", "flowspeech-ce-123-1", "flowspeech-remote-production"])
def test_cleanup_refuses_non_job_scope(monkeypatch, tmp_path, project):
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", project)
    monkeypatch.setattr(collect.subprocess, "run", lambda *a, **k: pytest.fail("Must not invoke Docker"))
    with pytest.raises(AssertionError, match="scope"):
        collect.cleanup(tmp_path)


def test_workflow_bounded_read_only_staging_order_cleanup_and_upload_guards():
    workflow = yaml.load((ROOT / ".github/workflows/remote-debug.yml").read_text(), Loader=yaml.BaseLoader)
    assert workflow["permissions"] == {"contents": "read"}
    paths = workflow["on"]["push"]["paths"]
    assert "scripts/deployed_ce/**" in paths and "scripts/verify_artifacts.py" in paths
    job = workflow["jobs"]["remote-debug"]
    assert job["timeout-minutes"] == "30" and "runner." not in json.dumps(job["env"])
    steps = job["steps"]
    assert "GATE_STATE" in steps[0]["run"] and "actions/checkout@" in steps[1]["uses"]
    commands = [s.get("run", "") for s in steps]
    stage_index = next(i for i, command in enumerate(commands) if "pip download" in command)
    up_index = next(i for i, command in enumerate(commands) if "up -d db" in command)
    assert stage_index < up_index
    assert "$GATE_STATE/plugin/requirements.txt" in commands[stage_index]
    assert not any("secrets." in json.dumps(step) or "upload/pkg" in step.get("run", "") for step in steps)
    cleanup = next(s for s in steps if "collect cleanup" in s.get("run", ""))
    assert cleanup["if"] == "always()"
    upload = steps[-1]
    assert "steps.logs.outcome == 'success'" in upload["if"] and "steps.evidence.outcome == 'success'" in upload["if"]
    assert upload["with"]["path"].endswith("/evidence/")
