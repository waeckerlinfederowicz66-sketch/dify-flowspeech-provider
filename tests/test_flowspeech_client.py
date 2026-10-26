import json

from flowspeech_client import FlowSpeechClient
from test_v1_contract import JOB, REQUEST, factory, job, response, wav_bytes


def test_audio_client(factory):
    core, calls, _, _ = factory([response(job())])
    with FlowSpeechClient("test-only", http_client=core._client, download_client=core._download,
                          clock=core.clock, sleep=core.sleep) as client:
        audio = client.generate_speech(text="Hello", voice_name="Kore", request_id=REQUEST)
    assert audio.content == wav_bytes() and audio.mime_type == "audio/wav"
    assert audio.job_id == JOB and audio.request_id == REQUEST
    assert json.loads(calls[0].content) == {"input": {"mode": "single", "text": "Hello", "voiceName": "Kore"}}

