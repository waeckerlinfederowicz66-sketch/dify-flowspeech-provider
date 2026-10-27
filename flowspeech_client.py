from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flowspeech_v1 import ApiError, V1Client, make_input

DEFAULT_BASE_URL = "https://flowspeech.io"
FlowSpeechError = ApiError


@dataclass(frozen=True)
class FlowSpeechAudio:
    content: bytes
    mime_type: str
    job_id: str
    request_id: str
    usage: dict[str, Any]


class FlowSpeechClient(V1Client):
    def __init__(self, api_key: str, **kwargs) -> None:
        super().__init__(api_key=api_key, user_agent="dify-flowspeech-provider/0.2.1", **kwargs)

    def check_quota(self) -> dict[str, Any]:
        return self.quota()["quota"]

    def list_voices(self):
        return self.voices()

    def generate_speech(self, *, text: str | None = None, voice_name: str = "Kore",
                        segments: list[dict[str, str]] | None = None,
                        request_id: str | None = None) -> FlowSpeechAudio:
        job, audio, request_id = self.generate(make_input(text, voice_name, segments), request_id=request_id)
        return FlowSpeechAudio(audio, "audio/wav", job["id"], request_id, job["usage"])
