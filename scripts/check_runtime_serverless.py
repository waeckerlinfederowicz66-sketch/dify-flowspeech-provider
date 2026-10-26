"""Smoke-test the actual SDK HTTP entrypoint on loopback, with all outbound HTTP mocked."""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx


def check(package, host_timeout):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    harness = Path(__file__).resolve().parents[1] / "tests" / "runtime_entrypoint_harness.py"
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(package),
           "PYTHONDONTWRITEBYTECODE": "1", "INSTALL_METHOD": "serverless",
           "SERVERLESS_HOST": "127.0.0.1", "SERVERLESS_PORT": str(port),
           "MAX_REQUEST_TIMEOUT": str(host_timeout), "MAX_WORKER": "2"}
    process = subprocess.Popen([sys.executable, "-u", str(harness), "success"],
                               cwd=package, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=10) as client:
            deadline = time.monotonic() + 15
            while True:
                try:
                    health = client.get(base + "/health")
                    assert health.status_code == 200 and health.text == "OK"
                    break
                except httpx.ConnectError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise AssertionError("SDK serverless entrypoint did not become healthy")
                    time.sleep(0.05)
            response = client.post(base + "/invoke", json={
                "event": "request", "session_id": "offline-http",
                "data": {"type": "tool", "action": "invoke_tool", "user_id": "offline-user",
                         "provider": "flowspeech", "tool": "flowspeech_text_to_speech",
                         "credentials": {"api_key": "test-only"},
                         "tool_parameters": {"text": "Offline test", "voice_name": "Kore",
                                             "request_id": "fedcbafe-5678-4def-8abc-fedcba987654", "timeout": 300}},
            })
            assert response.status_code == 200
            events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
            assert all(event["event"] == "session" and event["session_id"] == "offline-http" for event in events)
            assert events[-1]["data"]["type"] == "end"
            messages = [event["data"]["data"] for event in events if event["data"]["type"] == "stream"]
            if host_timeout == 300:
                chunks = [message["message"] for message in messages if message["type"] == "blob_chunk"]
                audio = b"".join(base64.b64decode(chunk["blob"]) for chunk in chunks)
                assert len(audio) == 18044 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"
                assert chunks[-1]["end"] and len(chunks) == 4
                result = next(message["message"]["json_object"] for message in messages if message["type"] == "json")
                assert result["job_id"] == "abcdefab-1234-4abc-8def-abcdef012345"
                assert result["request_id"] == "fedcbafe-5678-4def-8abc-fedcba987654"
            else:
                assert len(messages) == 1 and messages[0]["type"] == "text"
                text = messages[0]["message"]["text"]
                assert "abcdefab-1234-4abc-8def-abcdef012345" in text
                assert "fedcbafe-5678-4def-8abc-fedcba987654" in text
    finally:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=5)
    observations = []
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if "offline_observation" in value:
            observations.append(value["offline_observation"])
    calls = [item for item in observations if "method" in item]
    assert sum(item["method"] == "POST" for item in calls) == 1
    assert observations[0]["effective_timeout"] == host_timeout - 5
    assert max(item["elapsed"] for item in calls) == (200 if host_timeout == 300 else 170)
    print(json.dumps({"host_timeout": host_timeout, "effective_timeout": observations[0]["effective_timeout"],
                      "simulated_elapsed": max(item["elapsed"] for item in calls),
                      "health": "passed", "invoke": "audio" if host_timeout == 300 else "recovery_error",
                      "session_end": True, "real_outbound_connections": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=Path.cwd())
    package = parser.parse_args().package.resolve()
    for timeout in (300, 180):
        check(package, timeout)
