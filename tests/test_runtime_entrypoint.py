"""Exercise the real plugin process through the SDK's daemon-facing stdio protocol."""
import base64
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

import pytest
import yaml

import flowspeech_v1

JOB = "abcdefab-1234-4abc-8def-abcdef012345"
REQUEST = "fedcbafe-5678-4def-8abc-fedcba987654"


def invoke_runtime(scenario, *, host_timeout=300, validate=False):
    package_root = Path(flowspeech_v1.__file__).resolve().parent
    harness = Path(__file__).with_name("runtime_entrypoint_harness.py")
    request = {
        "session_id": "offline-session", "event": "request",
        "data": {"type": "tool", "action": "validate_tool_credentials" if validate else "invoke_tool",
                 "user_id": "offline-user", "provider": "flowspeech", "credentials": {"api_key": "test-only"}},
    }
    if not validate:
        request["data"].update(tool="flowspeech_text_to_speech", tool_parameters={
            "text": "Offline test", "voice_name": "Kore", "request_id": REQUEST, "timeout": 300,
        })
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(package_root),
           "PYTHONDONTWRITEBYTECODE": "1", "INSTALL_METHOD": "local",
           "MAX_REQUEST_TIMEOUT": str(host_timeout), "MAX_WORKER": "2",
           "HEARTBEAT_INTERVAL": "0.1"}
    process = subprocess.Popen([sys.executable, "-u", str(harness), scenario],
                               cwd=package_root, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    messages, raw, buffer = [], [], b""
    deadline = time.monotonic() + 15
    try:
        process.stdin.write(json.dumps(request).encode() + b"\n")
        process.stdin.flush()
        finished = False
        while time.monotonic() < deadline and not finished:
            ready, _, _ = select.select([process.stdout], [], [], max(0, deadline - time.monotonic()))
            if not ready:
                break
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                raw.append(line.decode(errors="replace"))
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                messages.append(message)
                if (message.get("event") == "session" and message.get("session_id") == "offline-session"
                        and message.get("data", {}).get("type") == "end"):
                    finished = True
        assert finished, "SDK entrypoint did not finish the session: " + "\n".join(raw)[-6000:]
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stdin.close()
        process.stdout.close()
    manifest = next(message for message in messages if message.get("type") == "plugin")
    assert manifest["name"] == "flowspeech" and manifest["version"] == "0.2.1"
    sessions = [message["data"] for message in messages if message.get("event") == "session"]
    observations = [message["offline_observation"] for message in messages if "offline_observation" in message]
    return sessions, observations


def test_actual_entrypoint_completes_200_second_job_and_serializes_wav_chunks():
    sessions, observations = invoke_runtime("success")
    assert sessions[-1]["type"] == "end"
    assert not any(message["type"] == "error" for message in sessions)
    streamed = [message["data"] for message in sessions if message["type"] == "stream"]
    chunks = [message["message"] for message in streamed if message["type"] == "blob_chunk"]
    assert [chunk["sequence"] for chunk in chunks] == [0, 1, 2, 3]
    assert chunks[-1]["end"] is True and chunks[-1]["blob"] == ""
    assert len({chunk["id"] for chunk in chunks}) == 1
    audio = b"".join(base64.b64decode(chunk["blob"]) for chunk in chunks)
    flowspeech_v1.validate_wav(audio)
    assert len(audio) == 18044 and all(chunk["total_length"] == len(audio) for chunk in chunks)
    result = next(message["message"]["json_object"] for message in streamed if message["type"] == "json")
    assert result["job_id"] == JOB and result["request_id"] == REQUEST
    assert observations[0]["effective_timeout"] == 295
    calls = [item for item in observations if "method" in item]
    assert sum(item["method"] == "POST" for item in calls) == 1
    assert len(calls) == 42 and calls[-1]["elapsed"] == 200
    assert {item["host"] for item in calls} == {"flowspeech.io", "static.flowspeech.io"}


@pytest.mark.parametrize("scenario,host", [("success", 180), ("malformed", 300)])
def test_actual_entrypoint_returns_recovery_error_and_session_end(scenario, host):
    sessions, observations = invoke_runtime(scenario, host_timeout=host)
    assert sessions[-1]["type"] == "end"
    messages = [item["data"] for item in sessions if item["type"] == "stream"]
    assert len(messages) == 1 and messages[0]["type"] == "text"
    assert JOB in messages[0]["message"]["text"] and REQUEST in messages[0]["message"]["text"]
    calls = [item for item in observations if "method" in item]
    assert sum(item["method"] == "POST" for item in calls) == 1
    if host == 180:
        assert observations[0]["effective_timeout"] == 175
        assert max(item["elapsed"] for item in calls) < 175
        assert all(item["host"] == "flowspeech.io" for item in calls)


@pytest.mark.parametrize("scenario,expected", [("credentials", "stream"), ("credential_error", "error")])
def test_actual_entrypoint_credential_validation_only_queries_quota(scenario, expected):
    sessions, observations = invoke_runtime(scenario, validate=True)
    assert sessions[0]["type"] == expected and sessions[-1]["type"] == "end"
    if expected == "stream":
        assert sessions[0]["data"] == {"result": True}
    calls = [item for item in observations if "method" in item]
    assert [(item["method"], item["path"]) for item in calls] == [("GET", "/api/v1/quota")]


def test_manifest_contains_verified_public_api_and_audio_hosts():
    manifest = yaml.safe_load((Path(flowspeech_v1.__file__).resolve().parent / "manifest.yaml").read_text())
    assert set(manifest["network"]["domains"]) == {"flowspeech.io", "static.flowspeech.io"}
