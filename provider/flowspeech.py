from typing import Any

import requests
from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from flowspeech_client import FlowSpeechClient, FlowSpeechError


class FlowSpeechProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        api_key = str(credentials.get("api_key") or "").strip()
        if not api_key:
            raise ToolProviderCredentialValidationError("FlowSpeech API key is required")
        try:
            FlowSpeechClient(api_key).check_quota()
        except FlowSpeechError as exc:
            raise ToolProviderCredentialValidationError(str(exc)) from exc
        except requests.RequestException as exc:
            raise ToolProviderCredentialValidationError(
                "Could not connect to the FlowSpeech API"
            ) from exc

