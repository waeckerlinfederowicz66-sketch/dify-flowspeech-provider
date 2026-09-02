from __future__ import annotations

import base64
import binascii
import io
import wave
from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_BASE_URL = "https://flowspeech.io"


class FlowSpeechError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class FlowSpeechAudio:
    content: bytes
    mime_type: str


class FlowSpeechClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        session: requests.Session | None = None,
        timeout: tuple[float, float] = (10.0, 170.0),
    ) -> None:
        if not api_key.strip():
            raise ValueError("FlowSpeech API key is required")
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "dify-flowspeech-provider/0.1.0",
        }

    def check_quota(self) -> dict[str, Any]:
        response = self._session.get(
            f"{self._base_url}/api/ai/text-to-speech/quota",
            headers=self._headers,
            timeout=self._timeout,
        )
        payload = self._read_response(response)
        quota = payload.get("data", {}).get("quota")
        if not isinstance(quota, dict):
            raise FlowSpeechError("FlowSpeech quota response did not include quota data")
        return quota

    def generate_speech(self, *, text: str, voice_name: str) -> FlowSpeechAudio:
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Text is required")
        if len(normalized_text) > 200_000:
            raise ValueError("Text must be 200,000 characters or fewer")
        normalized_voice = voice_name.strip() or "Kore"

        response = self._session.post(
            f"{self._base_url}/api/ai/text-to-speech",
            headers=self._headers,
            json={
                "text": normalized_text,
                "originalText": normalized_text,
                "speakers": [{"voiceName": normalized_voice}],
            },
            timeout=self._timeout,
        )
        payload = self._read_response(response)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise FlowSpeechError("FlowSpeech response did not include audio data")

        encoded_audio = data.get("audioBase64")
        if not isinstance(encoded_audio, str) or not encoded_audio.strip():
            raise FlowSpeechError("FlowSpeech response did not include audioBase64")
        try:
            audio = base64.b64decode(encoded_audio, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise FlowSpeechError("FlowSpeech returned invalid base64 audio") from exc

        mime_type = str(data.get("mimeType") or "audio/wav")
        if mime_type.lower().startswith(("audio/l16", "audio/pcm")):
            audio = self._pcm_to_wav(
                audio,
                sample_rate=self._positive_int(data.get("sampleRate"), 24_000),
                channels=self._positive_int(data.get("numChannels"), 1),
                bits_per_sample=self._positive_int(data.get("bitsPerSample"), 16),
            )
            mime_type = "audio/wav"

        return FlowSpeechAudio(content=audio, mime_type=mime_type)

    @staticmethod
    def _read_response(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise FlowSpeechError(
                "FlowSpeech returned a non-JSON response",
                status_code=response.status_code,
            ) from exc
        if not isinstance(payload, dict):
            raise FlowSpeechError(
                "FlowSpeech returned an invalid response",
                status_code=response.status_code,
            )
        if response.status_code >= 400 or payload.get("code") != 0:
            message = payload.get("message")
            raise FlowSpeechError(
                str(message or f"FlowSpeech returned HTTP {response.status_code}"),
                status_code=response.status_code,
            )
        return payload

    @staticmethod
    def _positive_int(value: Any, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    @staticmethod
    def _pcm_to_wav(
        audio: bytes,
        *,
        sample_rate: int,
        channels: int,
        bits_per_sample: int,
    ) -> bytes:
        if bits_per_sample % 8 != 0:
            raise FlowSpeechError("Unsupported PCM bit depth")
        output = io.BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(bits_per_sample // 8)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio)
        return output.getvalue()
