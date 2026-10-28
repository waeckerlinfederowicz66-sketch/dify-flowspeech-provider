# FlowSpeech for Dify

A Dify tool plugin for [FlowSpeech](https://flowspeech.io/) public API v1.
[Source repository](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider).

Version 0.2.1 adds bounded HTTP workers, deadline/retry corrections and
diagnostic privacy fixes.

## Setup

1. Create a FlowSpeech API key with an active paid Basic, Pro or Scale subscription.
2. Install `flowspeech-0.2.1.difypkg` in Dify and add the key in Dify's encrypted provider credentials.
3. Add Generate speech with FlowSpeech to a workflow.
4. Supply text and a voice, or omit text and supply a JSON array in Speaker segments.
5. Configure the tool deadline and Dify/plugin execution timeouts for the expected job duration.

The tool is a streaming generator. Once generation completes, it yields a WAV
audio blob and then a JSON message containing job_id, request_id and usage.
It does not stream partial audio during generation. It never wraps already encoded
WAV as raw PCM. Failed/deleted jobs emit a text error and no audio blob.

A fixed request UUID can recover an interrupted call only with identical text,
voice or segments. Leave it blank for a new recording. Never use one fixed UUID
for unrelated workflow executions. Errors include recovery IDs where available.

## Examples

Text: Welcome.[pause:2s]Let's begin. Voice: Kore.

For multiple speakers, omit text and set Speaker segments to:

```json
[
  {"speaker": "Alice", "text": "Welcome.", "voiceName": "Kore"},
  {"speaker": "Bob", "text": "Thank you.", "voiceName": "Puck"}
]
```

## Network and privacy

The tool accepts no custom API host or user-supplied download URL. The API origin
is fixed to https://flowspeech.io. Result URLs come only from authenticated job
responses and are downloaded separately without credentials. Runtime egress must
allow flowspeech.io and the result storage host (the manifest includes
static.flowspeech.io). Confirm your deployment allows the result host; the public
contract intentionally does not guarantee a specific storage domain.

The plugin has no independent local store, but Dify may retain workflow inputs,
outputs and persisted audio according to deployment settings. Text and speaker
segments supplied by the workflow author may contain personal information and
are sent to FlowSpeech without automatic redaction. See [plugin privacy details](PRIVACY.md),
the [FlowSpeech Privacy Policy](https://flowspeech.io/privacy-policy) and the
[public API documentation](https://flowspeech.io/docs/public-api) for service data
handling, retention and result-link access.

## API v1 behavior

An active paid Basic, Pro or Scale subscription and a FlowSpeech API key are
required; trials do not include API generation. Keep FLOWSPEECH_API_KEY server-side.
See [public API documentation](https://flowspeech.io/docs/public-api).

Generation submits POST /api/v1/tts/jobs with {"input": ...} and one UUID
Idempotency-Key, waits through queued/running/merging/settling, then downloads
result.url after success. A 200 response alone does not mean generation succeeded.
Single input uses mode/text/voiceName. Multi input uses mode/segments, where each
turn contains speaker, text and voiceName. Model, source, speed and format options
are unsupported and must not be sent.

The requested tool deadline defaults to 300 seconds. The effective deadline is
the smaller of that value and `MAX_REQUEST_TIMEOUT - 5` seconds. The five-second
margin lets the tool return audio or a recovery error before the host closes its
response. `MAX_REQUEST_TIMEOUT` is read from the Dify runtime environment at
startup (SDK default: 300 seconds), so the default effective tool deadline is
295 seconds. Set `MAX_REQUEST_TIMEOUT=600` before starting the plugin to allow a
full 300-second tool deadline, and configure any outer Dify workflow/proxy limits
accordingly. Host limits of five seconds or less are rejected before submission.
The plugin no longer hardcodes a 180-second timeout. It does not emit heartbeat
messages while generating; cancellation and timeout do not cancel the server job.

Polling is at least five seconds, and longer Retry-After values (seconds or HTTP
dates) are honored even when reading or closing the response body fails. A
received 401/403 is never retried. Transient transport failures, interrupted
success/5xx responses, 429, and complete explicitly retryable 5xx errors get at
most two retries. A complete 5xx response with retryable=false is not retried.
Create retries preserve the UUID and exact body. A deadline stops local waiting,
not the server job; use the saved IDs for recovery or explicit cancellation.

HTTP work is limited to eight active workers per plugin process and one per
client, without a queue. Saturation fails before network I/O with transport_busy
or client_busy; retain the same recovery UUID rather than creating a new job.
The caller still returns at its total deadline. A transport that does not return
can retain a worker slot until it finishes; a permanently stuck transport can
exhaust capacity and requires operator investigation. No new request is started
by an abandoned worker. Closing a client prevents new work and defers owned
transport cleanup until its active worker exits. Borrowed clients are never
closed by this adapter, and no server job is automatically cancelled.

Errors expose status_code, code, retryable, trace_id, request_id, job_id and
result_url where available. Failed and cancelled jobs raise errors. Deleted
success results are reported as result_deleted, not as empty audio.
HTTP diagnostics use fixed status messages, not upstream error text. Error codes
and trace IDs accept only bounded ASCII tokens that do not contain the configured
API key. Dify messages retain recovery IDs but do not print the programmatic
result_url attribute; treat that URL as sensitive and do not log exception dictionaries.

Audio is a separately downloaded, validated WAV (24000 Hz, mono, 16 bit).
Validation checks the entire RIFF size, every chunk boundary and alignment pad,
one PCM format/data pair, byte rate 48000, block alignment 2 and nonempty complete
16-bit samples. Malformed audio returns a structured error with recovery IDs.
Downloads use HTTPS without API Authorization, cookies, or default client
credentials, including across redirects. API redirects are rejected. Downloads
are bounded to 64 MiB by default. A download retry never submits another recording.
Anyone holding a result URL can access the recording; treat links as sensitive.

GET /api/v1/quota returns quota.remaining/reserved/available plus subscription
and limits. GET /api/v1/voices
returns voices. Recovery uses GET /api/v1/tts/jobs?requestId=UUID; status and cancel
use /api/v1/tts/jobs/{UUID} and /api/v1/tts/jobs/{UUID}/cancel.

## Development and packaging

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pytest==8.4.2
.venv/bin/python -m pytest -q
dify plugin package . -o dist/flowspeech-0.2.1.difypkg
```

The internal client now uses httpx. Test injection uses http_client and
download_client, replacing the old requests session argument. timeout is a total
seconds value, not a requests connect/read tuple.
