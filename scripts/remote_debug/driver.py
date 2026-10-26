"""Headless CE console tests of the official TCP remote-debug lifecycle."""
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
from urllib.error import HTTPError
import uuid

from scripts.deployed_ce import driver as ce
from scripts.deployed_ce.collect import redact

LIST = "/workspaces/current/plugin/list?page=1&page_size=100"
DEBUG_KEY = "/workspaces/current/plugin/debugging-key"
IDENTITY = re.compile(r"flowspeech/flowspeech:0\.2\.0@[0-9a-f]{64}\Z")


class Console(ce.Console):
    def json(self, path, **kwargs):
        assert "/upload/" not in path and "/install/" not in path, "Local package installation is forbidden"
        kwargs.setdefault("timeout", 15)
        result = super().json(path, **kwargs)
        if path == "/apps" and kwargs.get("method") == "POST":
            self.last_app_id = str(uuid.UUID(result["id"]))
        return result


def entries(console):
    items = console.json(LIST)["plugins"]
    assert isinstance(items, list) and len(items) <= 1, "Fresh workspace must have at most one debug plugin"
    for item in items:
        assert item.get("runtime_type") == "remote", "Local/serverless plugin fallback is forbidden"
        assert IDENTITY.fullmatch(item.get("plugin_unique_identifier", "")), "Unexpected plugin identity"
    return items


def bootstrap(console, state):
    setup = ce.wait_for(lambda: console.json("/setup"), 480)
    assert setup.get("step") == "not_started", "Refusing non-fresh CE workspace"
    console.json("/setup", method="POST", body={"email": console.fixture["email"],
                 "password": console.fixture["password"], "name": "Remote protocol CI", "language": "en-US"})
    console.login()
    initial = ce.wait_for(lambda: {"plugins": entries(console)}, 90)
    assert not initial["plugins"], "Workspace must start without installed plugins"
    response = ce.wait_for(lambda: console.json(DEBUG_KEY), 90)
    key = response.get("key")
    # Persist for redaction before inspecting any further response fields.
    if isinstance(key, str) and key:
        console.fixture["remote_debug_key"] = key
        (state / "fixture.json").write_text(json.dumps(console.fixture))
    assert isinstance(key, str) and str(uuid.UUID(key)) == key, "Invalid workspace debugging key"
    assert response.get("host") == "plugin_daemon" and response.get("port") == 5003, "Unexpected debug endpoint"
    (state / "remote-key").write_text(key)
    (state / "remote-key").chmod(0o600)
    return {"fresh_workspace": True, "initial_plugins": 0, "debug_key_acquired": True,
            "debug_endpoint": "plugin_daemon:5003", "local_install_calls": 0}


def connected(console, state):
    console.login()
    item = ce.wait_for(lambda: next(iter(entries(console)), None), 120)
    identity = item["plugin_unique_identifier"]
    readiness = ce.wait_for_runtime(console, 90)
    # Separate reset proves the valid save also performs quota validation only.
    console.control("/configure", {"case": "basic", "delay": 1})
    saved = console.json(ce.PROVIDER_PATH + "/add", method="POST", body={
        "credentials": {"api_key": console.fixture["api_key"]}, "name": "Remote fixture", "type": "api-key"})
    assert saved.get("result") == "success", "Valid provider credentials were not saved"
    console.json(ce.PROVIDER_PATH + "/info")
    tools = console.json(ce.PROVIDER_PATH + "/tools")
    assert any(tool.get("name") == "flowspeech_text_to_speech" for tool in tools)
    audit = console.control("/audit")
    assert not audit["jobs"] and audit["calls"], "Credential save must only validate quota"
    assert all(c["method"] == "GET" and c["path"] == "/api/v1/quota" and c["host"] == "flowspeech.io"
               and c["authorization_present"] and not c["cookie_present"] for c in audit["calls"])
    basic = ce.run_case(console, "basic", delay=1, timeout=300, expect_audio=True, minimum=4.8, maximum=60)
    assert entries(console)[0]["plugin_unique_identifier"] == identity
    # Keep the successful draft intact for the disconnect attempt; never create a replacement recording.
    (state / "dispatch.json").write_text(json.dumps({"app_id": console.last_app_id, "identity": identity}))
    return {"runtime_type": "remote", "plugin_unique_identifier": identity, "invalid_quota": readiness,
            "valid_credentials_saved": True, "valid_quota_audit": audit["calls"], "basic": basic}


def unavailable(message):
    return isinstance(message, str) and (
        "plugin provider " + ce.PROVIDER + " not found" in message
        or ("PluginDaemonInternalServerError" in message and "no available node, plugin runtime not found" in message))


def failed_dispatch(lines):
    failure = None
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        if not line.startswith("data:"):
            continue
        event = json.loads(line[5:].strip())
        if event.get("event") == "error":
            assert unavailable(event.get("message")), "Unrelated workflow error after disconnect"
            failure = event["message"]
        if event.get("event") == "workflow_finished":
            data = event["data"]
            assert data.get("status") == "failed", "Disconnected remote workflow unexpectedly completed"
            assert not (data.get("outputs") or {}).get("audio"), "Disconnected plugin returned audio"
            assert unavailable(data.get("error")), "Unrelated terminal failure after disconnect"
            failure = data["error"]
    assert failure is not None, "Missing explicit unavailable-plugin failure"
    return failure


def disconnected(console, state):
    console.login()
    started = time.monotonic()
    ce.wait_for(lambda: not entries(console), 90)
    dispatch = json.loads((state / "dispatch.json").read_text())
    app_id = str(uuid.UUID(dispatch["app_id"]))
    console.control("/configure", {"case": "basic", "delay": 1})
    try:
        with console.open(f"/apps/{app_id}/workflows/draft/run", method="POST", timeout=45,
                          body={"inputs": {}, "files": []}) as response:
            failure = failed_dispatch(response)
    except HTTPError as error:
        assert error.code in {400, 404}, "Unrelated HTTP failure after disconnect"
        body = error.read(65537)
        assert len(body) <= 65536
        failure = json.loads(body).get("message")
        assert unavailable(failure), "Unrelated HTTP error after disconnect"
    audit = console.control("/audit")
    assert audit["calls"] == [] and audit["jobs"] == {}, "Disconnected dispatch reached the API or storage"
    assert not entries(console), "A plugin fallback appeared after disconnect"
    return {"remote_registration_removed": True, "same_workflow_dispatch_failed": True,
            "failure": failure, "elapsed_seconds": round(time.monotonic() - started, 3),
            "remaining_plugins": 0, "creates": 0, "api_or_storage_calls": 0}


def main():
    assert os.getenv("GATE_ISOLATED") == "1"
    assert socket.gethostbyname("flowspeech.io") == socket.gethostbyname("mock")
    assert socket.gethostbyname("static.flowspeech.io") == socket.gethostbyname("mock")
    state = Path("/state")
    stage = sys.argv[1]
    operation = {"bootstrap": bootstrap, "connected": connected, "disconnected": disconnected}[stage]
    fixture = json.loads((state / "fixture.json").read_text())
    console = Console(fixture)
    report = {"status": "failed", "stage": stage}
    try:
        report["result"] = operation(console, state)
        report["status"] = "passed"
    except Exception as error:
        report["error_type"] = type(error).__name__
        report["error"] = redact(str(error), list(fixture.values()))[:2000]
        raise RuntimeError(f"Remote gate failed during {stage}: {type(error).__name__}") from None
    finally:
        (state / "evidence" / (stage + ".json")).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"stage": stage, "status": report["status"]}))


if __name__ == "__main__":
    main()
