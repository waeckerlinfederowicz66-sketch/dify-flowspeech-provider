"""HTTPS fixture reached through the unchanged plugin's production hostnames."""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import ssl
import threading
import time
from urllib.parse import urlsplit
import uuid
import wave


def fixture_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 9000)
    return output.getvalue()


class State:
    def __init__(self, api_key: str, clock=time.monotonic):
        self.api_key, self.clock = api_key, clock
        self.calls: list[dict] = []
        self.jobs: dict[str, dict] = {}
        self.case, self.delay = "basic", 1.0

    def configure(self, case: str, delay: float):
        if case not in {"basic", "slow", "malformed", "deadline", "api-redirect", "audio-redirect"}:
            raise ValueError("Unknown fixture case")
        if not 0 <= delay <= 240:
            raise ValueError("Fixture delay outside bounded gate")
        self.case, self.delay = case, delay
        self.calls.clear()
        self.jobs.clear()

    def handle(self, method: str, host: str, path: str, headers: dict, body: bytes):
        headers = {k.lower(): v for k, v in headers.items()}
        call = {"method": method, "host": host, "path": path,
                "authorization_present": "authorization" in headers,
                "cookie_present": "cookie" in headers, "elapsed": self.clock(),
                "request_id": headers.get("idempotency-key"),
                "body_sha256": hashlib.sha256(body).hexdigest()}
        self.calls.append(call)
        error = lambda status, code: (status, {}, {"error": {"code": code, "message": code, "retryable": False}})
        if host == "static.flowspeech.io":
            if call["authorization_present"] or call["cookie_present"]:
                return error(403, "FIXTURE_CREDENTIAL_LEAK")
            if method != "GET" or not path.startswith("/audio/"):
                return error(404, "FIXTURE_UNEXPECTED_DOWNLOAD")
            if self.case == "audio-redirect":
                return 302, {"Location": "https://flowspeech.io/redirect-target"}, b""
            content = b"not-a-riff-file" if self.case == "malformed" else fixture_wav()
            return 200, {"Content-Type": "audio/wav"}, content
        if host != "flowspeech.io":
            return error(403, "FIXTURE_UNEXPECTED_HOST")
        if headers.get("authorization") != "Bearer " + self.api_key:
            return error(401, "INVALID_API_KEY")
        if method == "GET" and path == "/api/v1/quota":
            return 200, {}, {"quota": {"remaining": 1000, "reserved": 0, "available": 1000},
                             "subscription": {"status": "active"}, "limits": {}}
        if method == "POST" and path == "/api/v1/tts/jobs":
            request_id = str(uuid.UUID(headers["idempotency-key"]))
            payload = json.loads(body)
            assert set(payload) == {"input"}
            assert payload["input"] == {"mode": "single", "text": "CE fixture " + self.case, "voiceName": "Kore"}
            if self.case == "api-redirect":
                return 302, {"Location": "https://flowspeech.io/redirect-target"}, b""
            job_id = str(uuid.uuid4())
            self.jobs[job_id] = {"id": job_id, "requestId": request_id, "started": self.clock()}
            return 202, {}, self.job(job_id)
        if method == "GET" and path.startswith("/api/v1/tts/jobs/"):
            return 200, {}, self.job(path.rsplit("/", 1)[-1])
        return error(404, "FIXTURE_UNEXPECTED_PATH")

    def job(self, job_id: str):
        item = self.jobs[job_id]
        done = self.clock() - item["started"] >= self.delay
        return {"id": job_id, "requestId": item["requestId"], "status": "success" if done else "queued",
                "usage": {"billableCharacters": 10, "reservedCredits": 0, "chargedCredits": 10 if done else 0},
                "result": {"url": "https://static.flowspeech.io/audio/" + job_id + ".wav",
                           "mimeType": "audio/wav", "sampleRate": 24000, "channels": 1, "bitsPerSample": 16}
                if done else None}


def serve():
    config = json.loads(Path("/fixture.json").read_text())
    state = State(config["api_key"])
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def dispatch(self):
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 65536:
                self.send_error(413)
                return
            body = self.rfile.read(length)
            host = self.headers.get("Host", "").split(":", 1)[0]
            path = urlsplit(self.path).path
            with lock:
                try:
                    if self.server.server_port == 8080:
                        if self.headers.get("X-Gate-Control") != config["control_key"]:
                            status, headers, result = 403, {}, {"error": "fixture control denied"}
                        elif self.command == "POST" and path == "/configure":
                            state.configure(**json.loads(body))
                            status, headers, result = 200, {}, {"ok": True}
                        elif self.command == "GET" and path == "/audit":
                            status, headers, result = 200, {}, {"calls": state.calls, "jobs": state.jobs}
                        else:
                            status, headers, result = 404, {}, {"error": "fixture control path"}
                    else:
                        status, headers, result = state.handle(self.command, host, path, dict(self.headers), body)
                except (KeyError, ValueError, AssertionError):
                    status, headers, result = 422, {}, {"error": "fixture contract violation"}
                if not isinstance(result, bytes):
                    result = json.dumps(result).encode()
                    headers["Content-Type"] = "application/json"
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(result)))
                self.end_headers()
                self.wfile.write(result)

        do_GET = dispatch
        do_POST = dispatch

    https = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain("/fixture-ca.crt", "/fixture-ca.key")
    https.socket = context.wrap_socket(https.socket, server_side=True)
    control = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    threading.Thread(target=control.serve_forever, daemon=True).start()
    https.serve_forever()


if __name__ == "__main__":
    serve()
