from collections.abc import Generator
from typing import Any

import requests
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from flowspeech_client import FlowSpeechClient, FlowSpeechError


class FlowSpeechTextToSpeechTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        api_key = str(self.runtime.credentials.get("api_key") or "").strip()
        text = str(tool_parameters.get("text") or "").strip()
        voice_name = str(tool_parameters.get("voice_name") or "Kore").strip()

        if not api_key:
            yield self.create_text_message("FlowSpeech API key is not configured")
            return
        if not text:
            yield self.create_text_message("Text is required")
            return

        try:
            audio = FlowSpeechClient(api_key).generate_speech(
                text=text,
                voice_name=voice_name,
            )
        except FlowSpeechError as exc:
            yield self.create_text_message(f"FlowSpeech request failed: {exc}")
            return
        except requests.RequestException:
            yield self.create_text_message("Could not connect to the FlowSpeech API")
            return
        except ValueError as exc:
            yield self.create_text_message(str(exc))
            return

        yield self.create_blob_message(
            audio.content,
            meta={"mime_type": audio.mime_type},
        )

