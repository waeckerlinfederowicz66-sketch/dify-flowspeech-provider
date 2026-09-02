import base64
import io
import wave

import pytest
import requests

from flowspeech_client import FlowSpeechClient, FlowSpeechError


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, *, get_response=None, post_response=None):
        self.get_response = get_response
        self.post_response = post_response
        self.last_request = None

    def get(self, url, **kwargs):
        self.last_request = ("GET", url, kwargs)
        return self.get_response

    def post(self, url, **kwargs):
        self.last_request = ("POST", url, kwargs)
        return self.post_response


def test_check_quota_uses_bearer_token():
    session = FakeSession(
        get_response=FakeResponse(
            {"code": 0, "data": {"quota": {"remaining": 1200}}}
        )
    )
    quota = FlowSpeechClient("test-key", session=session).check_quota()

    assert quota["remaining"] == 1200
    method, url, kwargs = session.last_request
    assert method == "GET"
    assert url.endswith("/api/ai/text-to-speech/quota")
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"


def test_generate_speech_sends_expected_payload_and_wraps_pcm_as_wav():
    pcm = b"\x00\x00\x01\x00" * 20
    session = FakeSession(
        post_response=FakeResponse(
            {
                "code": 0,
                "data": {
                    "audioBase64": base64.b64encode(pcm).decode("ascii"),
                    "mimeType": "audio/L16;rate=24000",
                    "sampleRate": 24000,
                    "numChannels": 1,
                    "bitsPerSample": 16,
                },
            }
        )
    )
    audio = FlowSpeechClient("test-key", session=session).generate_speech(
        text="[warmly] Welcome to the update.", voice_name="Charon"
    )

    assert audio.mime_type == "audio/wav"
    with wave.open(io.BytesIO(audio.content), "rb") as wav_file:
        assert wav_file.getframerate() == 24000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.readframes(wav_file.getnframes()) == pcm

    method, url, kwargs = session.last_request
    assert method == "POST"
    assert url.endswith("/api/ai/text-to-speech")
    assert kwargs["json"] == {
        "text": "[warmly] Welcome to the update.",
        "originalText": "[warmly] Welcome to the update.",
        "speakers": [{"voiceName": "Charon"}],
    }


def test_generate_speech_preserves_encoded_audio():
    encoded = b"ID3-test-audio"
    session = FakeSession(
        post_response=FakeResponse(
            {
                "code": 0,
                "data": {
                    "audioBase64": base64.b64encode(encoded).decode("ascii"),
                    "mimeType": "audio/mpeg",
                },
            }
        )
    )
    audio = FlowSpeechClient("test-key", session=session).generate_speech(
        text="Hello", voice_name="Kore"
    )

    assert audio.content == encoded
    assert audio.mime_type == "audio/mpeg"


@pytest.mark.parametrize("status", [401, 429, 500])
def test_api_errors_include_status(status):
    session = FakeSession(
        get_response=FakeResponse(
            {"code": -1, "message": "request rejected"}, status_code=status
        )
    )
    with pytest.raises(FlowSpeechError) as exc_info:
        FlowSpeechClient("test-key", session=session).check_quota()

    assert exc_info.value.status_code == status
    assert str(exc_info.value) == "request rejected"


def test_non_json_response_is_rejected():
    session = FakeSession(get_response=FakeResponse(ValueError("not json"), 502))
    with pytest.raises(FlowSpeechError, match="non-JSON"):
        FlowSpeechClient("test-key", session=session).check_quota()


def test_text_limit_is_enforced_before_request():
    with pytest.raises(ValueError, match="200,000"):
        FlowSpeechClient("test-key", session=FakeSession()).generate_speech(
            text="x" * 200_001,
            voice_name="Kore",
        )

