from types import SimpleNamespace

import pytest
import yaml

from flowspeech_client import FlowSpeechAudio, FlowSpeechError
from provider.flowspeech import FlowSpeechProvider
from tools import text_to_speech
from test_v1_contract import JOB, REQUEST, wav_bytes


class FakeClient:
    error = None
    captured = None
    closed = False

    def __init__(self, api_key, **kwargs):
        assert api_key == "test-only"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        type(self).closed = True

    def generate_speech(self, **kwargs):
        type(self).captured = kwargs
        if self.error:
            raise self.error
        return FlowSpeechAudio(wav_bytes(), "audio/wav", JOB, REQUEST, {"chargedCredits": 5})


def tool_context():
    return SimpleNamespace(runtime=SimpleNamespace(credentials={"api_key": "test-only"}),
        create_blob_message=lambda data, meta: ("blob", data, meta),
        create_json_message=lambda data: ("json", data),
        create_text_message=lambda data: ("text", data))


def test_tool_yields_audio_blob_and_recovery_metadata(monkeypatch):
    monkeypatch.setattr(text_to_speech, "FlowSpeechClient", FakeClient)
    FakeClient.error = None
    generator = text_to_speech.FlowSpeechTextToSpeechTool._invoke(
        tool_context(), {"text": "Hello", "request_id": REQUEST})
    assert iter(generator) is generator
    messages = list(generator)
    assert messages[0] == ("blob", wav_bytes(), {"mime_type": "audio/wav", "filename": "speech.wav"})
    assert messages[1][1]["job_id"] == JOB
    assert FakeClient.closed


def test_tool_failure_yields_no_audio(monkeypatch):
    monkeypatch.setattr(text_to_speech, "FlowSpeechClient", FakeClient)
    FakeClient.error = FlowSpeechError("failed", request_id=REQUEST, job_id=JOB)
    messages = list(text_to_speech.FlowSpeechTextToSpeechTool._invoke(tool_context(), {"text": "Hello"}))
    assert len(messages) == 1 and messages[0][0] == "text"
    assert REQUEST in messages[0][1] and JOB in messages[0][1]
    FakeClient.error = None


def test_tool_multi_segments(monkeypatch):
    monkeypatch.setattr(text_to_speech, "FlowSpeechClient", FakeClient)
    list(text_to_speech.FlowSpeechTextToSpeechTool._invoke(tool_context(),
        {"segments": '[{"speaker":"Alice","text":"Hi","voiceName":"Kore"}]'}))
    assert FakeClient.captured["segments"][0]["speaker"] == "Alice"
    assert FakeClient.captured["text"] is None


def test_manifest_and_tool_schema():
    from pathlib import Path
    root = Path(text_to_speech.__file__).resolve().parents[1]
    manifest = yaml.safe_load((root / "manifest.yaml").read_text())
    tool = yaml.safe_load((root / "tools/text_to_speech.yaml").read_text())
    assert manifest["version"] == "0.2.0"
    assert "static.flowspeech.io" in manifest["network"]["domains"]
    assert {p["name"] for p in tool["parameters"]} >= {"text", "voice_name", "segments", "request_id", "timeout"}


def test_real_sdk_message_objects(monkeypatch):
    from dify_plugin.entities.tool import ToolInvokeMessage
    monkeypatch.setattr(text_to_speech, "FlowSpeechClient", FakeClient)
    tool = text_to_speech.FlowSpeechTextToSpeechTool.from_credentials({"api_key": "test-only"})
    messages = list(tool._invoke({"text": "Hello"}))
    assert all(isinstance(message, ToolInvokeMessage) for message in messages)
    assert messages[0].type.value == "blob"
    assert messages[0].message.blob == wav_bytes()
    assert messages[0].meta["mime_type"] == "audio/wav"
    assert messages[1].type.value == "json"
    assert messages[1].message.json_object["request_id"] == REQUEST


def test_provider_validation_uses_only_quota(monkeypatch):
    import provider.flowspeech as provider
    class QuotaClient(FakeClient):
        def check_quota(self):
            return {"remaining": 10, "available": 10, "reserved": 0}
        def generate_speech(self, **kwargs):
            raise AssertionError("credential validation must never generate")
    monkeypatch.setattr(provider, "FlowSpeechClient", QuotaClient)
    provider.FlowSpeechProvider._validate_credentials(None, {"api_key": "test-only"})


def test_tool_rejects_obsolete_options():
    messages = list(text_to_speech.FlowSpeechTextToSpeechTool._invoke(tool_context(), {"text": "Hello", "model": "obsolete"}))
    assert messages[0][0] == "text" and "Unsupported" in messages[0][1]


def test_real_sdk_manifest_provider_and_tool_schemas(monkeypatch):
    from pathlib import Path
    from dify_plugin.core.entities.plugin.setup import PluginConfiguration
    from dify_plugin.entities.tool import ToolConfiguration, ToolProviderConfiguration
    root = Path(text_to_speech.__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    manifest = PluginConfiguration.model_validate(yaml.safe_load((root / "manifest.yaml").read_text()))
    provider = ToolProviderConfiguration.model_validate(yaml.safe_load((root / "provider/flowspeech.yaml").read_text()))
    tool = ToolConfiguration.model_validate(yaml.safe_load((root / "tools/text_to_speech.yaml").read_text()))
    assert manifest.version == "0.2.0" and manifest.meta.version == "0.1.0"
    assert provider.tools[0].identity.name == tool.identity.name

