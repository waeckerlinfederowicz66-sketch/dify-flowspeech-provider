"""Offline host/tool deadline integration, including a 200-second job."""
import runpy
from pathlib import Path
from queue import Empty
from unittest.mock import patch

import httpx
import pytest
from dify_plugin.core.server.serverless import request_reader as serverless

import runtime_config
from flowspeech_client import FlowSpeechClient
from test_tool import tool_context
from test_v1_contract import JOB, REQUEST, factory, job, response, wav_bytes
from tools import text_to_speech


@pytest.fixture(autouse=True)
def clean_startup_config(monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_TIMEOUT", "300")
    runtime_config.get_plugin_env.cache_clear()
    yield
    runtime_config.get_plugin_env.cache_clear()


def test_entrypoint_honors_environment_without_starting_a_server(monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_TIMEOUT", "600")
    captured = []
    monkeypatch.setattr("dify_plugin.Plugin", lambda config: captured.append(config))
    runpy.run_path(str(Path(text_to_speech.__file__).resolve().parents[1] / "main.py"))
    assert captured[0].MAX_REQUEST_TIMEOUT == 600
    assert captured[0] is runtime_config.get_plugin_env()


@pytest.mark.parametrize("host,requested,expected", [
    ("300", None, 295), ("600", None, 300), ("600", 500, 500),
    ("180", 300, 175), ("300", 20, 20), ("600", 1000, 595),
])
def test_tool_deadline_reserves_host_response_margin(monkeypatch, host, requested, expected):
    monkeypatch.setenv("MAX_REQUEST_TIMEOUT", host)
    assert runtime_config.effective_tool_timeout(requested) == expected


@pytest.mark.parametrize("requested", [0, -1, float("nan"), float("inf"), True, "bad"])
def test_invalid_tool_deadlines_are_rejected(requested):
    with pytest.raises(ValueError):
        runtime_config.effective_tool_timeout(requested)


@pytest.mark.parametrize("host", ["0", "-1", "5"])
def test_host_without_response_margin_fails_before_submitting(monkeypatch, host):
    monkeypatch.setenv("MAX_REQUEST_TIMEOUT", host)
    def unexpected(*args, **kwargs):
        raise AssertionError("No client should be created")
    monkeypatch.setattr(text_to_speech, "FlowSpeechClient", unexpected)
    messages = list(text_to_speech.FlowSpeechTextToSpeechTool._invoke(tool_context(), {"text": "Hello"}))
    assert len(messages) == 1 and messages[0][0] == "text" and "MAX_REQUEST_TIMEOUT" in messages[0][1]


def inject_client(monkeypatch, core):
    captured = []
    def create(api_key, **kwargs):
        captured.append(kwargs["timeout"])
        return FlowSpeechClient(api_key, http_client=core._client, download_client=core._download,
                                clock=core.clock, sleep=core.sleep, **kwargs)
    monkeypatch.setattr(text_to_speech, "FlowSpeechClient", create)
    return captured


def test_200_second_job_completes_with_the_real_client_and_sdk_messages(factory, monkeypatch):
    # Forty five-second polls put completion after the former 180-second cutoff.
    core, calls, downloads, clock = factory(
        [response(job("queued")) for _ in range(40)] + [response(job())])
    captured = inject_client(monkeypatch, core)
    tool = text_to_speech.FlowSpeechTextToSpeechTool.from_credentials({"api_key": "test-only"})
    messages = list(tool._invoke({"text": "Hello", "request_id": REQUEST}))
    assert clock.now == 200 and captured == [295]
    assert [message.type.value for message in messages] == ["blob", "json"]
    assert messages[0].message.blob == wav_bytes()
    assert messages[1].message.json_object["job_id"] == JOB
    assert messages[1].message.json_object["request_id"] == REQUEST
    assert len(calls) == 41 and len(downloads) == 1
    assert sum(request.method == "POST" for request in calls) == 1


def test_shorter_host_gets_recovery_error_before_its_response_closes(factory, monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_TIMEOUT", "180")
    core, calls, downloads, clock = factory([response(job("queued")) for _ in range(40)])
    captured = inject_client(monkeypatch, core)
    messages = list(text_to_speech.FlowSpeechTextToSpeechTool._invoke(
        tool_context(), {"text": "Hello", "request_id": REQUEST, "timeout": 300}))
    assert captured == [175] and clock.now < 175 < 180
    assert len(messages) == 1 and messages[0][0] == "text"
    assert REQUEST in messages[0][1] and JOB in messages[0][1]
    assert not downloads and sum(request.method == "POST" for request in calls) == 1


def test_serverless_response_stays_open_for_200_seconds_using_actual_sdk(monkeypatch):
    # The real serverless reader's idle-close logic, with no socket or real waiting.
    host = runtime_config.get_plugin_env().MAX_REQUEST_TIMEOUT
    reader = serverless.ServerlessRequestReader(max_single_connection_lifetime=host)
    now = [0]
    class DelayedResponseQueue:
        @classmethod
        def __class_getitem__(cls, _):
            return cls
        def get(self, timeout=None):
            if now[0] < 200:
                now[0] += 1
                raise Empty
            return "completed-audio" if now[0] == 200 else None
        def put(self, value):
            pass

    with reader.app.test_request_context("/invoke", method="POST", json={
        "event": "request", "session_id": "offline-test", "data": {},
    }), patch.object(serverless, "Queue", DelayedResponseQueue), patch.object(serverless.time, "time", lambda: now[0]):
        stream, status = reader.handler()
        assert status == 200 and next(stream) == "completed-audio" and now[0] == 200
        now[0] += 1
        with pytest.raises(StopIteration):
            next(stream)


def test_malformed_wav_becomes_tool_error_without_a_blob(factory, monkeypatch):
    core, calls, downloads, _ = factory(
        [response(job())], [httpx.Response(200, content=b"RIFF\x0c\0\0\0WAVEJUNK\x64\0\0\0")])
    inject_client(monkeypatch, core)
    messages = list(text_to_speech.FlowSpeechTextToSpeechTool._invoke(
        tool_context(), {"text": "Hello", "request_id": REQUEST}))
    assert len(messages) == 1 and messages[0][0] == "text"
    assert REQUEST in messages[0][1] and JOB in messages[0][1]
    assert len(calls) == len(downloads) == 1
