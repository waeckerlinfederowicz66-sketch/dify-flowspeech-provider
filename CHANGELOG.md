# Changelog

## 0.2.0 - 2026-10-26

- Require requestId on every job response; normalize job/request UUIDs before comparison and return canonical lowercase IDs.

- Release-gate fix: structurally validate RIFF/chunk bounds and exact PCM WAV fields; reject partial samples and preserve recovery IDs on all malformed-audio errors.
- Release-gate fix: honor MAX_REQUEST_TIMEOUT from the environment and cap the tool deadline below the host timeout, with simulated 200-second completion coverage.

- Migrate from legacy synchronous generation to public API v1 submit, poll and download.
- Add stable UUID idempotency, bounded retries, Retry-After, total deadlines and recovery IDs.
- Map single and explicit multi-speaker input; reject obsolete options and malformed responses.
- Validate success/deleted states, WAV metadata and downloaded audio; bound download sizes.
- Isolate download credentials across HTTPS redirects; reject API redirects.
- Update quota/voices handling, subscription requirements and error diagnostics.
- Add fake-transport contract tests and distribution verification.
- Preserve generator-based audio blob output; add multi-speaker JSON, request UUID and deadline controls.
- Switch the internal client transport from requests to httpx; update storage egress declaration.

The 0.2.0 release assets are prepared locally. Publication is a separate coordinator action.

