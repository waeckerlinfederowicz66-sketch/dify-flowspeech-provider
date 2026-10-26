from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from flowspeech_client import FlowSpeechClient, FlowSpeechError


class FlowSpeechProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            with FlowSpeechClient(str(credentials.get("api_key") or ""), timeout=30) as client:
                client.check_quota()
        except (FlowSpeechError, ValueError) as exc:
            raise ToolProviderCredentialValidationError(str(exc)) from exc

