# Plugin Submission

Local coordinator draft only; updating this file does not change the public PR.
Current candidate: immutable Marketplace commit
`1024cfe3385e390626e0e4253b23d4c6b9469651`. New-hash deployed validation is pending.

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

- Source pytest suite: 386 passed; replacement extracted package: 188 passed.
- Six new subprocess/manifest checks exercise the real SDK stdio registration,
  invocation, credential validation, WAV chunk serialization and session end.
- Real SDK serverless HTTP /health and /invoke pass against source and the package
  using loopback plus mocked outbound HTTP. A simulated 200-second job completes
  with host 300/tool 295; host 180/tool 175 returns recovery IDs at simulated 170.
- 2 existing SDK test warnings: gevent SSL import ordering and Pydantic Config deprecation.
- Archive audit: 17 members, 126197 bytes; no prohibited development files, secret
  patterns, private local paths or executable tooling.
- Package SHA-256: 5fc5942eac8185e17f4150da74aceeed2a7c08f935f55b93597f1968a12f05f4.
- Public version metadata on 2026-10-26: 0.1.0 exists; 0.2.0 not found.

## Reviewer notes

This is a draft update pending complete Dify deployment/remote-debugging
validation required by the development guidelines. The unchecked guidelines
item is deliberate; direct SDK tests do not substitute for that requirement.

The previous package (`ae19e420...c3384`) passed actual isolated CE run 40326427753
and remote-debug run 40336384519 attempt 2, including cleanup. The replacement
changes only README/PRIVACY; all runtime members are byte-identical, but those old
passes do not validate its new archive hash. Both deployed gates must run again.
Cloud, browser/UI, production services and managed egress policy remain unvalidated
and are documented limitations, not claimed passes. No live generation is claimed.

Breaking behavior is documented in the packaged README: the API now uses
asynchronous jobs; legacy model/source/speed/format options are rejected; output
is validated WAV; a paid eligible subscription/API key is required. Polling and
download use one total deadline, with recovery identifiers on failures.

Complete the remaining deployment validation before marking the guidelines
checkbox and requesting review. Preserve the one-package PR scope.
