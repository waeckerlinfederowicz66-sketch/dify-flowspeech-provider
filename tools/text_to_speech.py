import json
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from flowspeech_client import FlowSpeechClient, FlowSpeechError
from runtime_config import effective_tool_timeout


class FlowSpeechTextToSpeechTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        api_key = str(self.runtime.credentials.get("api_key") or "")
        text = tool_parameters.get("text") or None
        voice_name = tool_parameters.get("voice_name") or "Kore"
        try:
            unknown = set(tool_parameters) - {"text", "voice_name", "segments", "request_id", "timeout"}
            if unknown:
                raise ValueError("Unsupported synthesis options: " + ", ".join(sorted(unknown)))
            raw_segments = tool_parameters.get("segments")
            segments = json.loads(raw_segments) if isinstance(raw_segments, str) and raw_segments.strip() else raw_segments or None
            timeout = effective_tool_timeout(tool_parameters.get("timeout"))
            with FlowSpeechClient(api_key, timeout=timeout) as client:
                audio = client.generate_speech(text=text, voice_name=voice_name, segments=segments,
                                              request_id=tool_parameters.get("request_id") or None)
        except FlowSpeechError as exc:
            recovery = f" request_id={exc.request_id} job_id={exc.job_id}" if exc.request_id else ""
            yield self.create_text_message(f"FlowSpeech request failed: {exc}.{recovery}")
            return
        except (TypeError, ValueError) as exc:
            yield self.create_text_message(str(exc))
            return

        yield self.create_blob_message(audio.content, meta={"mime_type": audio.mime_type, "filename": "speech.wav"})
        yield self.create_json_message({"job_id": audio.job_id, "request_id": audio.request_id, "usage": audio.usage})

