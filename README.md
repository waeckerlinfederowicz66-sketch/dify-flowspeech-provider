# FlowSpeech for Dify

FlowSpeech for Dify is a tool plugin that turns workflow text into an audio file through the [FlowSpeech text-to-speech API](https://flowspeech.io/).

Source repository: [waeckerlinfederowicz66-sketch/dify-flowspeech-provider](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider)

## What it does

- Generates context-aware speech from text in a Dify workflow.
- Exposes 30 FlowSpeech voices, including Kore, Puck, Charon, Aoede, and Fenrir.
- Preserves FlowSpeech emotion cues and pause tags passed in the input text.
- Converts raw PCM responses to standard WAV files so downstream Dify nodes can consume the result.
- Keeps the FlowSpeech API key in Dify's encrypted provider credentials.

## Setup

1. Create a FlowSpeech API key in your FlowSpeech account.
2. Install this plugin in Dify.
3. Open **Plugins**, select **FlowSpeech**, and add the API key.
4. Add **Generate speech with FlowSpeech** to a workflow.
5. Connect text from an LLM, template, knowledge workflow, or form and choose a voice.

The tool returns one audio blob. The MIME type is preserved for encoded audio; raw PCM is wrapped in a WAV container.

## Example workflow

Use an LLM or template node to produce narration text, then pass it to FlowSpeech:

```text
[warmly] Welcome to the weekly product briefing. [⌛1.0s]
Today we will review the three changes that affect your team.
```

Choose `Charon` for an informative narration style or `Kore` for a firm, focused delivery. Store the returned audio with a file node or send it to any downstream integration that accepts Dify file output.

## Data handling

The plugin sends only the synthesis text, selected voice, and authentication header to `https://flowspeech.io`. It does not write audio, text, or credentials to local plugin storage. See [PRIVACY.md](PRIVACY.md).

## Connection requirements

The Dify plugin runtime must be able to make outbound HTTPS requests to `https://flowspeech.io` on port 443. The plugin does not contact user-selected hosts and does not accept arbitrary endpoint URLs.

## Development

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/pytest -q
```

Package the plugin with the Dify plugin CLI:

```bash
dify plugin package .
```

## License

MIT
