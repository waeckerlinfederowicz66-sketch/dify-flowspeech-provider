"""Install and exercise the reviewed package through a disposable CE console API."""
from __future__ import annotations

import argparse
import base64
import hashlib
from http.cookiejar import CookieJar
import io
import json
import os
from pathlib import Path
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, ProxyHandler, Request, build_opener
import uuid
import wave

if __package__:
    from .collect import redact
    from .mock_http import fixture_wav
else:
    from collect import redact
    from mock_http import fixture_wav

BASE = "http://api:5001"
PROVIDER = "flowspeech/flowspeech/flowspeech"
PROVIDER_PATH = "/workspaces/current/tool-provider/builtin/" + PROVIDER


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def graph(case: str, request_id: str, timeout: float) -> dict:
    nodes = [
        {"id": "start", "type": "custom", "position": {"x": 0, "y": 0},
         "data": {"type": "start", "title": "Start", "variables": []}},
        {"id": "speech", "type": "custom", "position": {"x": 300, "y": 0},
         "data": {"type": "tool", "title": "FlowSpeech", "version": "1",
                  "provider_type": "builtin", "provider_id": PROVIDER, "provider_name": "flowspeech",
                  "tool_name": "flowspeech_text_to_speech", "tool_label": "Generate speech with FlowSpeech",
                  "tool_configurations": {"voice_name": "Kore", "request_id": request_id, "timeout": timeout},
                  "tool_parameters": {"text": {"type": "mixed", "value": "CE fixture " + case}}}},
        {"id": "end", "type": "custom", "position": {"x": 600, "y": 0},
         "data": {"type": "end", "title": "End", "outputs": [
             {"variable": "audio", "value_selector": ["speech", "files"], "value_type": "array[file]"},
             {"variable": "metadata", "value_selector": ["speech", "json"], "value_type": "array[object]"},
             {"variable": "message", "value_selector": ["speech", "text"], "value_type": "string"}]}}
    ]
    edges = [{"id": a + "-" + b, "source": a, "target": b, "sourceHandle": "source",
              "targetHandle": "target", "type": "custom",
              "data": {"sourceType": kind_a, "targetType": kind_b, "isInIteration": False}}
             for a, b, kind_a, kind_b in [("start", "speech", "start", "tool"), ("speech", "end", "tool", "end")]]
    return {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 1}}


def terminal_event(lines) -> dict:
    final = None
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        if not line.startswith("data:"):
            continue
        event = json.loads(line[5:].strip())
        if event.get("event") == "error":
            raise AssertionError("CE workflow error: " + str(event.get("message", event.get("code", "unknown"))))
        if event.get("event") == "workflow_finished":
            final = event["data"]
    if final is None or final.get("status") != "succeeded":
        raise AssertionError("CE workflow did not finish successfully: " + str((final or {}).get("error", "missing terminal event")))
    return final


def file_url(value: str) -> str:
    if value.startswith("/files/"):
        value = BASE + value
    url = urlsplit(value)
    if (url.scheme != "http" or url.hostname != "api" or url.port != 5001
            or url.username is not None or url.password is not None or not url.path.startswith("/files/")):
        raise ValueError("Refusing a file URL outside this disposable CE instance")
    return value


class Console:
    def __init__(self, fixture: dict):
        self.fixture = fixture
        self.cookies = CookieJar()
        self.opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPCookieProcessor(self.cookies))

    def open(self, path, *, method="GET", body=None, headers=None, timeout=420):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Console path must remain local")
        headers = dict(headers or {})
        csrf = next((c.value for c in self.cookies if c.name.endswith("csrf_token")), None)
        if csrf:
            headers["X-CSRF-Token"] = csrf
        if isinstance(body, dict):
            body = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        return self.opener.open(Request(BASE + "/console/api" + path, body, headers, method=method), timeout=timeout)

    def json(self, path, **kwargs):
        with self.open(path, **kwargs) as response:
            return json.load(response)

    def login(self):
        result = self.json("/login", method="POST", body={
            "email": self.fixture["email"],
            "password": base64.b64encode(self.fixture["password"].encode()).decode(), "remember_me": False})
        if result.get("result") != "success" or not any(c.name.endswith("csrf_token") for c in self.cookies):
            raise AssertionError("CE login or CSRF cookie failed")

    def control(self, path, payload=None):
        headers = {"X-Gate-Control": self.fixture["control_key"]}
        data = None if payload is None else json.dumps(payload).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request("http://mock:8080" + path, data, headers)
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=10) as response:
            return json.load(response)


def wait_for(check, seconds=300):
    deadline = time.monotonic() + seconds
    while True:
        try:
            result = check()
            if result:
                return result
        except HTTPError as error:
            if error.code not in {408, 429, 500, 502, 503, 504}:
                raise
        except (URLError, ConnectionError, TimeoutError):
            pass
        if time.monotonic() >= deadline:
            raise TimeoutError("Disposable CE readiness/install deadline exceeded")
        time.sleep(3)


def install(console: Console, state: Path) -> dict:
    status = wait_for(lambda: console.json("/setup"), 600)
    if status.get("step") != "not_started":
        raise AssertionError("Refusing to bootstrap a non-fresh CE instance")
    console.json("/setup", method="POST", body={"email": console.fixture["email"],
                 "password": console.fixture["password"], "name": "CI validation", "language": "en-US"})
    console.login()
    package = (state / "candidate.difypkg").read_bytes()
    pins = json.loads((Path(__file__).parent / "pins.json").read_text())
    assert hashlib.sha256(package).hexdigest() == pins["package_sha256"]
    boundary = "ce-gate-" + uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"pkg\"; filename=\"flowspeech-0.2.0.difypkg\""
            "\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + package + f"\r\n--{boundary}--\r\n".encode()
    uploaded = console.json("/workspaces/current/plugin/upload/pkg", method="POST", body=body,
                            headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    identity = uploaded["unique_identifier"]
    assert identity.startswith("flowspeech/flowspeech:0.2.0@")
    console.json("/workspaces/current/plugin/install/pkg", method="POST",
                 body={"plugin_unique_identifiers": [identity]})

    def installed():
        entries = console.json("/workspaces/current/plugin/list?page=1&page_size=100")["plugins"]
        return next((entry for entry in entries if entry.get("plugin_unique_identifier") == identity), None)

    item = wait_for(installed, 480)
    assert item.get("runtime_type") == "local", "The real local Go daemon runtime is required"
    return {"stage": "installed", "package_sha256": pins["package_sha256"],
            "plugin_unique_identifier": identity, "runtime_type": item["runtime_type"]}


def run_case(console, case, *, delay, timeout, expect_audio, minimum=0, maximum=420):
    console.current_case = case
    console.current_audit = None
    console.control("/configure", {"case": case, "delay": delay})
    request_id = str(uuid.uuid4())
    app = console.json("/apps", method="POST", body={"name": "FlowSpeech CE " + case, "mode": "workflow"})
    app_id = str(uuid.UUID(app["id"]))
    console.json(f"/apps/{app_id}/workflows/draft", method="POST",
                 body={"graph": graph(case, request_id, timeout), "features": {}})
    started = time.monotonic()
    with console.open(f"/apps/{app_id}/workflows/draft/run", method="POST",
                      body={"inputs": {}, "files": []}) as response:
        final = terminal_event(response)
    elapsed = time.monotonic() - started
    assert minimum <= elapsed < maximum, "Workflow did not respect the expected wall-clock bounds"
    outputs = final["outputs"]
    assert console.fixture["api_key"] not in json.dumps(outputs), "Credential leaked to workflow output"
    files = outputs.get("audio") or []
    audit = console.control("/audit")
    console.current_audit = audit
    calls = audit["calls"]
    creates = [c for c in calls if c["method"] == "POST"]
    assert len(creates) == 1 and creates[0]["path"] == "/api/v1/tts/jobs"
    assert creates[0]["request_id"] == request_id
    assert all(c["path"] != "/redirect-target" for c in calls), "A forbidden redirect was followed"
    polls = [c for c in calls if c["path"].startswith("/api/v1/tts/jobs/")]
    if polls:
        assert polls[0]["elapsed"] - creates[0]["elapsed"] >= 4.8
        assert all(b["elapsed"] - a["elapsed"] >= 4.8 for a, b in zip(polls, polls[1:]))
    downloads = [c for c in calls if c["host"] == "static.flowspeech.io" or c["path"] == "/audio/redirected.wav"]
    assert all(not c["authorization_present"] and not c["cookie_present"] for c in downloads)
    job_id = next(iter(audit["jobs"]), None)
    persisted_audio_sha256 = None
    if expect_audio:
        assert len(files) == 1 and len(downloads) == (2 if case == "audio-redirect-safe" else 1)
        if case == "audio-redirect-safe":
            assert [(c["host"], c["path"]) for c in downloads] == [
                ("static.flowspeech.io", "/audio/" + job_id + ".wav"),
                ("flowspeech.io", "/audio/redirected.wav")]
        metadata = json.dumps(outputs.get("metadata"))
        assert request_id in metadata and job_id in metadata
        # Download only from CE's file service, not from the mock storage directly.
        url = file_url(files[0]["url"])
        with console.opener.open(url, timeout=15) as response:
            audio = response.read(1024 * 1024)
        assert audio == fixture_wav(), "CE's persisted WAV differs from the plugin's fixture output"
        persisted_audio_sha256 = hashlib.sha256(audio).hexdigest()
        with wave.open(io.BytesIO(audio), "rb") as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (24000, 1, 2)
    else:
        assert not files
        assert request_id in outputs.get("message", "")
        if job_id:
            assert job_id in outputs["message"]
    return {"case": case, "workflow_status": final["status"], "elapsed_seconds": round(elapsed, 3),
            "request_id": request_id, "job_id": job_id, "creates": len(creates), "polls": len(polls),
            "downloads": len(downloads), "audio_files": len(files),
            "persisted_audio_sha256": persisted_audio_sha256, "audit": calls}


def run(console, *, short_host=False, progress=None):
    results = progress if progress is not None else []
    console.current_case = "provider-readiness"
    console.login()
    # CE's /info requires saved credentials; /tools only requires the installed plugin.
    tools = wait_for(lambda: console.json(PROVIDER_PATH + "/tools"), 120)
    assert isinstance(tools, list) and any(tool.get("name") == "flowspeech_text_to_speech" for tool in tools)
    if short_host:
        assert os.environ["GATE_HOST_TIMEOUT"] == "180"
        console.current_case = "provider-saved-credentials"
        wait_for(lambda: console.json(PROVIDER_PATH + "/info"), 120)
        results.append(run_case(console, "deadline", delay=200, timeout=300, expect_audio=False, minimum=160, maximum=180))
        return results
    assert os.environ["GATE_HOST_TIMEOUT"] == "300"
    console.control("/configure", {"case": "basic", "delay": 1})
    console.current_case = "provider-invalid-credentials"
    invalid_rejected = False
    try:
        result = console.json(PROVIDER_PATH + "/add", method="POST", body={
            "credentials": {"api_key": "invalid-fixture-key"}, "name": "Rejected fixture", "type": "api-key"})
        invalid_rejected = result.get("result") != "success"
    except HTTPError as error:
        invalid_rejected = error.code in {400, 401, 403}
    assert invalid_rejected, "CE accepted invalid provider credentials"
    audit = console.control("/audit")["calls"]
    assert audit and all(c["method"] == "GET" and c["path"] == "/api/v1/quota" for c in audit)
    console.current_case = "provider-valid-credentials"
    result = console.json(PROVIDER_PATH + "/add", method="POST", body={
        "credentials": {"api_key": console.fixture["api_key"]}, "name": "Isolated fixture", "type": "api-key"})
    assert result["result"] == "success"
    console.current_case = "provider-saved-credentials"
    wait_for(lambda: console.json(PROVIDER_PATH + "/info"), 120)
    tools = console.json(PROVIDER_PATH + "/tools")
    assert isinstance(tools, list) and any(tool.get("name") == "flowspeech_text_to_speech" for tool in tools)
    results.append({"case": "provider-credentials", "invalid_rejected": True, "valid_saved": True})
    for case, delay, timeout, expect, minimum, maximum in [
        ("basic", 1, 300, True, 4.8, 60),
        ("slow", 200, 300, True, 199, 295),
        ("malformed", 1, 300, False, 0, 60),
        ("api-redirect", 1, 300, False, 0, 30),
        ("audio-redirect", 1, 300, False, 0, 60),
        ("audio-redirect-safe", 1, 300, True, 4.8, 60),
        ("deadline", 200, 10, False, 4, 15),
    ]:
        results.append(run_case(console, case, delay=delay, timeout=timeout, expect_audio=expect,
                                minimum=minimum, maximum=maximum))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["install", "run", "short-host"])
    args = parser.parse_args()
    if os.getenv("GATE_ISOLATED") != "1":
        raise RuntimeError("Run only in the isolated Compose driver container")
    assert socket.gethostbyname("flowspeech.io") == socket.gethostbyname("mock")
    assert socket.gethostbyname("static.flowspeech.io") == socket.gethostbyname("mock")
    state = Path("/state")
    fixture = json.loads((state / "fixture.json").read_text())
    console = Console(fixture)
    result = {"stage": args.stage, "status": "failed", "cloud_validated": False, "results": []}
    try:
        if args.stage == "install":
            result["results"] = install(console, state)
        else:
            run(console, short_host=args.stage == "short-host", progress=result["results"])
        result["status"] = "passed"
    except Exception as error:
        # Credentials/cookies and raw responses never enter retained diagnostics.
        result["error_type"] = type(error).__name__
        result["error_message"] = redact(str(error), list(fixture.values()))[:2000]
        result["current_case"] = getattr(console, "current_case", None)
        if getattr(console, "current_audit", None) is not None:
            result["failed_case_audit"] = console.current_audit
        if isinstance(error, HTTPError):
            result["http_status"] = error.code
            result["route"] = urlsplit(error.url).path
        raise RuntimeError(f"CE gate failed during {args.stage}: {type(error).__name__}") from None
    finally:
        (state / "evidence" / (args.stage + ".json")).write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"stage": args.stage, "status": result["status"]}), flush=True)


if __name__ == "__main__":
    main()
