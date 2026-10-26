# Plugin Submission

## Plugin information

- **Author**: flowspeech
- **Plugin name**: flowspeech
- **Version**: 0.2.0
- **Source repository**: https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider
- **Contact**: support@flowspeech.io

## Submission type

- [ ] New plugin
- [x] Version update

## What changed

Updates the plugin previously accepted in #3008 (merged, not pending).
Migrates generation to FlowSpeech public API v1 submit/poll/download with stable
UUID idempotency, bounded retries, total deadlines and recoverable request/job IDs.
Validates complete PCM WAV structure and isolates credentials from audio downloads.
Requires requestId on all jobs and normalizes UUID case. Honors Dify's configured
host deadline and caps the tool five seconds below it.

This PR adds only flowspeech/flowspeech/flowspeech-0.2.0.difypkg; 0.1.0 is preserved.

## Risk level

- [ ] Low risk
- [x] Medium risk
- [ ] High risk

User-supplied speech text/segments are sent to a third-party HTTPS API, which
creates a recording and may consume account credits. Result URLs grant access
to audio and must be treated as sensitive.

## Required checks

- [x] I have read and followed the [Marketplace submission requirements](https://github.com/langgenius/dify-plugins/blob/main/docs/plugin-submission-requirements.md).
- [ ] I have read and comply with the [Plugin Development Guidelines](https://docs.dify.ai/en/develop-plugin/publishing/standards/contributor-covenant-code-of-conduct).
- [x] I tested this plugin on Dify Community Edition and Dify Cloud, or documented any limitation below.
- [x] The package contains only files needed at runtime.
- [x] The package does not contain secrets, local credentials, .env files, .git directories, virtual environments, caches, logs, or IDE files.
- [x] The package does not contain executables or bundled binaries.
- [x] The plugin README includes setup steps, usage instructions, required APIs or credentials, connection requirements, and the source repository link.
- [x] The plugin includes PRIVACY.md, and manifest.yaml references it.
- [x] All user-facing text is primarily in English, with localized labels where provided.

## Security and privacy notes

No command/code execution, SQL, database access, browser automation, filesystem
tools or user-configurable network destinations are exposed. The tool sends user
text and voice choices to FlowSpeech. Downloads follow server-issued HTTPS result
URLs and validated HTTPS redirects, with no Bearer tokens, cookies or injected
client credentials. API redirects are refused; responses and deadlines are bounded.

Declared hosts are flowspeech.io and static.flowspeech.io. The latter is confirmed
by the public homepage's demo WAV assets and a credential-free HEAD returning
200 audio/wav without a redirect. Scoped public-domain configuration agrees.
No real credentials, private input or production generation was used in testing.

## Local validation

- Source pytest suite: 188 passed; reviewed extracted package: 188 passed.
- Six new subprocess/manifest checks exercise the real SDK stdio registration,
  invocation, credential validation, WAV chunk serialization and session end.
- Real SDK serverless HTTP /health and /invoke pass against source and the package
  using loopback plus mocked outbound HTTP. A simulated 200-second job completes
  with host 300/tool 295; host 180/tool 175 returns recovery IDs at simulated 170.
- 2 existing SDK test warnings: gevent SSL import ordering and Pydantic Config deprecation.
- Archive audit: 17 members, 125757 bytes; no prohibited development files, secret
  patterns, private local paths or executable tooling.
- Package SHA-256: ae19e4209a5b9693ca4435df4b0fa8dc3017e4648e6e69743c2452bb0f0c3384.
- Public version metadata on 2026-10-26: 0.1.0 exists; 0.2.0 not found.

## Reviewer notes

This is a draft update pending complete Dify deployment/remote-debugging
validation required by the development guidelines. The unchecked guidelines
item is deliberate; direct SDK tests do not substitute for that requirement.

No complete Dify CE or Cloud installation or external Go daemon was exercised.
Docker is unavailable in the test environment; the actual Python SDK entrypoints
were used directly. A workspace reviewer/operator must still confirm installed
plugin behavior, deployed timeout/egress enforcement and any admin storage-domain
override. No live generation is claimed. Any on-platform production generation
requires separately approved credentials and credits.

Breaking behavior is documented in the packaged README: the API now uses
asynchronous jobs; legacy model/source/speed/format options are rejected; output
is validated WAV; a paid eligible subscription/API key is required. Polling and
download use one total deadline, with recovery identifiers on failures.

Complete the remaining deployment validation before marking the guidelines
checkbox and requesting review. Preserve the one-package PR scope.
