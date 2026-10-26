# Privacy Policy

Last updated: October 26, 2026

The plugin sends synthesis text or ordered speaker segments, selected voices,
a request UUID and the configured API key to FlowSpeech over HTTPS for speech
generation, authentication and job recovery. Text, speaker labels and segments
supplied by the workflow author may contain personal information, such as names
or contact details. The plugin does not remove personal information from these
inputs before transmitting them to FlowSpeech.

The key is sent only to flowspeech.io in the Authorization header. Dify stores
provider credentials according to the security controls of the user's deployment.
Dify may also retain workflow inputs, outputs and persisted audio according to
that deployment's settings.

The plugin polls job metadata and downloads the completed WAV from the HTTPS
result URL returned by FlowSpeech, potentially on a separate storage host.
Downloads and redirects never carry the API key, cookies or API credentials.
Result links are accessible to anyone holding the URL and should be kept private.

The plugin has no independent local store for input text, generated audio or
credentials. Audio, job/request IDs and usage are returned to the Dify workflow;
this does not prevent Dify or FlowSpeech from retaining data. FlowSpeech's data
handling is described in its [Privacy Policy](https://flowspeech.io/privacy-policy).
See the [public API documentation](https://flowspeech.io/docs/public-api) for
script, task metadata and audio retention and result-link access. Local timeout
does not cancel an accepted server job.

Users should submit only content they are authorized to send to FlowSpeech and
avoid including unnecessary personal information.
Privacy contact: support@flowspeech.io.

