"""Synthetic upstream diagnostics must not reach Dify messages or tracebacks."""
import traceback

import httpx
import pytest

from flowspeech_client import FlowSpeechClient
from flowspeech_v1 import ApiError
from provider import flowspeech as provider
from tools import text_to_speech
from test_v1_contract import INPUT, JOB, REQUEST, factory, job, response

KEY = "test-only"
PRIVATE_URL = "https://audio.example.test/a.wav?signature=synthetic-private-link"
PRIVATE_TEXT = "synthetic private recording text"
UNSAFE_TOKENS = [KEY, "prefix_" + KEY, PRIVATE_URL, "line\nbreak", {"token": KEY}, [KEY], 7, "x" * 129]


@pytest.mark.parametrize("token", UNSAFE_TOKENS)
def test_api_error_tokens_and_message_are_safe(factory, token):
    client, _, _, _ = factory([response({
        "error": {"code": token, "message": PRIVATE_TEXT + " " + PRIVATE_URL, "retryable": False},
        "traceId": token,
    }, 403)])
    with pytest.raises(ApiError) as caught:
        client.generate(INPUT, request_id=REQUEST)
    error = caught.value
    assert error.code == "http_error" and error.trace_id is None
    assert error.status_code == 403 and not error.retryable and error.request_id == REQUEST
    rendered = str(error) + repr(error) + "".join(traceback.format_exception(error))
    assert all(value not in rendered for value in (KEY, PRIVATE_URL, PRIVATE_TEXT))


@pytest.mark.parametrize("token", UNSAFE_TOKENS)
@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_terminal_error_tokens_are_safe(factory, token, status):
    client, _, downloads, _ = factory([response(job(status, error={"code": token, "message": PRIVATE_URL}))])
    with pytest.raises(ApiError) as caught:
        client.generate(INPUT, request_id=REQUEST)
    assert caught.value.code == status and caught.value.job_id == JOB and caught.value.request_id == REQUEST
    assert not downloads and PRIVATE_URL not in str(caught.value)


def test_safe_diagnostic_tokens_are_preserved(factory):
    client, _, _, _ = factory([response({"error": {"code": "insufficient_credits", "message": PRIVATE_TEXT,
                                                "retryable": False}, "traceId": JOB}, 403)])
    with pytest.raises(ApiError) as caught:
        client.generate(INPUT, request_id=REQUEST)
    assert caught.value.code == "insufficient_credits" and caught.value.trace_id == JOB
    assert str(caught.value) == "FlowSpeech API returned HTTP 403"


@pytest.mark.parametrize("stage", ["api", "terminal", "download"])
def test_real_tool_messages_do_not_reflect_error_fields(monkeypatch, stage):
    calls = []

    def handle(request):
        calls.append(request)
        if stage == "api":
            return response({"error": {"code": KEY, "message": PRIVATE_URL + " " + PRIVATE_TEXT,
                                       "retryable": False}, "traceId": KEY}, 403)
        if stage == "terminal":
            return response(job("failed", error={"code": KEY, "message": PRIVATE_URL}))
        if request.method == "POST":
            payload = job()
            payload["result"]["url"] = PRIVATE_URL
            return response(payload)
        return httpx.Response(403)

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        monkeypatch.setattr(text_to_speech, "FlowSpeechClient", lambda api_key, **kwargs: FlowSpeechClient(
            api_key, http_client=transport, download_client=transport, **kwargs))
        tool = text_to_speech.FlowSpeechTextToSpeechTool.from_credentials({"api_key": KEY})
        messages = list(tool._invoke({"text": "Synthetic", "request_id": REQUEST}))
    assert len(messages) == 1 and messages[0].type.value == "text"
    rendered = messages[0].model_dump_json()
    assert all(value not in rendered for value in (KEY, PRIVATE_URL, PRIVATE_TEXT))
    assert REQUEST in rendered
    if stage != "api":
        assert JOB in rendered
    assert len(calls) == (2 if stage == "download" else 1)


def test_provider_exception_chain_does_not_reflect_upstream_message(monkeypatch):
    calls = []

    def handle(request):
        calls.append(request)
        return response({"error": {"code": KEY, "message": PRIVATE_URL + " " + PRIVATE_TEXT,
                                   "retryable": False}, "traceId": KEY}, 401)

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        monkeypatch.setattr(provider, "FlowSpeechClient", lambda api_key, **kwargs: FlowSpeechClient(
            api_key, http_client=transport, download_client=transport, **kwargs))
        with pytest.raises(provider.ToolProviderCredentialValidationError) as caught:
            provider.FlowSpeechProvider._validate_credentials(None, {"api_key": KEY})
    rendered = "".join(traceback.format_exception(caught.value))
    assert all(value not in rendered for value in (KEY, PRIVATE_URL, PRIVATE_TEXT))
    assert [request.url.path for request in calls] == ["/api/v1/quota"]


def test_result_url_remains_available_only_as_explicit_recovery_metadata(factory):
    payload = job()
    payload["result"]["url"] = PRIVATE_URL
    client, _, _, _ = factory([response(payload)], [httpx.Response(403)])
    with pytest.raises(ApiError) as caught:
        client.generate(INPUT, request_id=REQUEST)
    assert caught.value.result_url == PRIVATE_URL
    assert caught.value.request_id == REQUEST and caught.value.job_id == JOB
    assert PRIVATE_URL not in str(caught.value) + repr(caught.value)
