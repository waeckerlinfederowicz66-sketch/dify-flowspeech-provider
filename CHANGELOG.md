# Changelog

## Unreleased - Local Review Candidate

- Use fixed HTTP diagnostics and bounded safe code/trace tokens so upstream
  messages, reflected keys and private audio links do not enter Dify error output.
- Preserve HTTP status and Retry-After through response-body and close failures;
  never retry received 401/403 responses, and keep retries within the total deadline.
- Bound HTTP workers across clients; reject saturation without queuing, prevent
  abandoned workers from submitting requests, and defer owned-client cleanup.
- Add offline source/artifact regressions for retry policy, recovery IDs,
  credential-free downloads, worker saturation and late submission prevention.
- Version metadata remains 0.2.0. These changes are not in the previously
  submitted package and have not been published or deployment-tested.

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

