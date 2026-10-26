"""One startup configuration shared by the Dify host and its tool deadline."""
from functools import lru_cache

from dify_plugin import DifyPluginEnv

from flowspeech_v1 import positive

RESPONSE_MARGIN_SECONDS = 5.0
DEFAULT_TOOL_TIMEOUT = 300.0


@lru_cache(maxsize=1)
def get_plugin_env() -> DifyPluginEnv:
    return DifyPluginEnv()


def effective_tool_timeout(value=None) -> float:
    if isinstance(value, bool):
        raise ValueError("timeout must be a finite positive number")
    requested = positive(float(DEFAULT_TOOL_TIMEOUT if value is None else value), "timeout")
    host_timeout = positive(get_plugin_env().MAX_REQUEST_TIMEOUT, "MAX_REQUEST_TIMEOUT")
    if host_timeout <= RESPONSE_MARGIN_SECONDS:
        raise ValueError("MAX_REQUEST_TIMEOUT must exceed the five-second response margin")
    return min(requested, host_timeout - RESPONSE_MARGIN_SECONDS)
