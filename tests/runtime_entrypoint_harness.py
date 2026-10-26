"""Run the unmodified SDK/main stdio loop with offline HTTP and a fake job clock."""
import dify_plugin  # Apply SDK gevent setup before importing HTTP/socket modules.

import io
import json
import os
import runpy
import socket
import sys
import wave

import httpx

import flowspeech_v1

JOB = "abcdefab-1234-4abc-8def-abcdef012345"
REQUEST = "fedcbafe-5678-4def-8abc-fedcba987654"
SCENARIO = sys.argv[1]
NOW = [0.0]


def blocked(*args, **kwargs):
    raise AssertionError("No socket connections are allowed in entrypoint tests")


socket.socket.connect = blocked
socket.socket.connect_ex = blocked


def report(**data):
    print(json.dumps({"offline_observation": data}), flush=True)


def sleep(seconds):
    NOW[0] += seconds


output = io.BytesIO()
with wave.open(output, "wb") as audio:
    audio.setnchannels(1)
    audio.setsampwidth(2)
    audio.setframerate(24000)
    audio.writeframes(b"\0\0" * 9000)
WAV = output.getvalue()


def handle(request):
    host, path = request.url.host, request.url.path
    report(method=request.method, host=host, path=path, elapsed=NOW[0])
    if host == "static.flowspeech.io":
        assert request.method == "GET" and path == "/offline-fixture.wav"
        assert not {"authorization", "cookie", "x-api-key"} & set(request.headers)
        content = WAV if SCENARIO != "malformed" else b"RIFF\x0c\0\0\0WAVEJUNK\x64\0\0\0"
        return httpx.Response(200, content=content, headers={"Content-Type": "audio/wav"})
    assert host == "flowspeech.io"
    assert request.headers["Authorization"] == "Bearer test-only"
    if path == "/api/v1/quota":
        if SCENARIO == "credential_error":
            return httpx.Response(401, json={"error": {"code": "unauthorized", "message": "Rejected", "retryable": False}})
        return httpx.Response(200, json={"quota": {"remaining": 100, "reserved": 0, "available": 100},
                                        "subscription": {"plan": "basic"}, "limits": {}})
    assert path in ("/api/v1/tts/jobs", "/api/v1/tts/jobs/" + JOB)
    if request.method == "POST":
        assert request.headers["Idempotency-Key"] == REQUEST
        assert json.loads(request.content) == {"input": {"mode": "single", "text": "Offline test", "voiceName": "Kore"}}
    else:
        assert request.method == "GET"
    status = "success" if SCENARIO == "malformed" or NOW[0] >= 200 else "queued"
    return httpx.Response(200, json={
        "id": JOB, "requestId": REQUEST, "status": status,
        "usage": {"billableCharacters": 12, "reservedCredits": 0, "chargedCredits": 12},
        "result": {"url": "https://static.flowspeech.io/offline-fixture.wav", "mimeType": "audio/wav",
                   "sampleRate": 24000, "channels": 1, "bitsPerSample": 16},
    })


original_http_init = httpx.Client.__init__


def offline_http_init(self, *args, **kwargs):
    kwargs["transport"] = httpx.MockTransport(handle)
    kwargs["trust_env"] = False
    original_http_init(self, *args, **kwargs)


httpx.Client.__init__ = offline_http_init
original_v1_init = flowspeech_v1.V1Client.__init__


def timed_v1_init(self, *args, **kwargs):
    kwargs.update(clock=lambda: NOW[0], sleep=sleep)
    original_v1_init(self, *args, **kwargs)
    report(effective_timeout=self.timeout, host_timeout=int(os.environ["MAX_REQUEST_TIMEOUT"]))


flowspeech_v1.V1Client.__init__ = timed_v1_init
# No SDK registration, routing, serialization or run-loop methods are mocked.
runpy.run_path("main.py", run_name="__main__")
