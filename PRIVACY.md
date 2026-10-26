# Privacy Policy

Last updated: October 26, 2026

The plugin sends synthesis text or ordered speaker segments, selected voices,
a request UUID and the configured API key to FlowSpeech over HTTPS. The key is
sent only to flowspeech.io in the Authorization header. Dify stores provider
credentials according to the security controls of the user's deployment.

The plugin polls job metadata and downloads the completed WAV from the HTTPS
result URL returned by FlowSpeech, potentially on a separate storage host.
Downloads and redirects never carry the API key, cookies or API credentials.
Result links are accessible to anyone holding the URL and should be kept private.

The plugin does not persist input text, generated audio or credentials in local
storage. Audio, job/request IDs and usage are returned to the Dify workflow.
FlowSpeech retains scripts, task metadata and audio according to its published
API retention policy. Local timeout does not cancel an accepted server job.

Users should submit only content they are authorized to process.
Privacy contact: support@flowspeech.io.

