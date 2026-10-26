# Release 0.2.0

## Current deployed-validation handoff

Marketplace update PR [3513](https://github.com/langgenius/dify-plugins/pull/3513)
is open and draft. Do not mark deployed CE or Cloud validation complete based on
the SDK/source suites. The new `Deployed CE release gate` workflow is prepared,
not executed. Its 24 offline harness checks pass within the 212-test source suite.
The reviewed 125757-byte package remains unchanged at SHA-256
`ae19e4209a5b9693ca4435df4b0fa8dc3017e4648e6e69743c2452bb0f0c3384`.

Coordinator: review and push the scoped workflow, harness, test and report changes
to `codex/public-api-v1`; that push triggers the first bounded CE job. No secret
configuration is needed. Follow `scripts/deployed_ce/README.md` for exact run/watch/
download commands, failure evidence, cleanup and the separate Cloud access gate.
The workstation has no container runtime; no deployed pass is claimed locally.
Do not expand this first run to paid APIs, external deployments or browser sessions.

Before a new commit, verify local `user.email` is
`waeckerlinfederowicz66@gmail.com`. Preserve user.name, global configuration and
published history. The worker does not push or dispatch CI.

## Coordinator steps

1. Review the changed source and VALIDATION.md; no user changes existed initially.
2. Re-run .venv/bin/python -m pytest -q using Python 3.12 and requirements.txt.
3. Use Dify Plugin CLI 0.6.12:
   .tools/dify plugin package . -o dist/flowspeech-0.2.0.difypkg
4. Inspect the archive and validate its manifest/schema and real SDK blob output.
5. The intended storage hostname is verified as static.flowspeech.io; see
   VALIDATION.md for public asset and scoped configuration evidence. Confirm the
   deployed daemon/proxy permits flowspeech.io and static.flowspeech.io and aligns
   execution deadlines. An admin storage override still needs operator confirmation.
6. Install in a reviewer-accessible Dify workspace for a workflow smoke test.
   Paid generation requires separately approved credentials and credits.
7. Publish source/release only from the coordinator. Submit the Marketplace version
   update using the project's existing authorized process.

## Marketplace status correction

GET https://api.github.com/repos/langgenius/dify-plugins/pulls/3008 on 2026-10-26
returned state=closed, merged=true, merged_at=2026-09-02T12:49:13Z,
merge_commit_sha=e815a9ec4182159a2fab8ed973288cfe589c63fe.
Its original head was waeckerlinfederowicz66-sketch/dify-plugins:add-flowspeech-plugin.

Do not claim #3008 is pending or try to update it as an open submission.
The coordinator followed the Marketplace version-update process in draft PR
3513, referencing the merged original. The deployment release gate is still open.

## Packaging tool provenance

Official asset:
https://github.com/langgenius/dify-plugin-daemon/releases/download/0.6.12/dify-plugin-darwin-arm64

SHA-256 (verified before execution, matches GitHub release asset digest):
c730a27b118d1342ac5650f99155033110f394f5a6dbf3023689328bf921efb6

The executable lives only in ignored .tools/ and is excluded by .difyignore.

## Safety gates

No production API key or paid generation was used. Do not enable live generation
during routine packaging tests. Do not include .env, credentials, virtualenvs,
caches, tool executables, downloaded reference wheels or private content in releases.
Review VALIDATION.md for exact results and remaining integration limitations.

Preserve the existing 0.1.0 publication. Release 0.2.0 only after final coordinator
review of source, artifacts, registry availability and account authorization.
The worker has not pushed commits, published packages or changed any upstream PR.

The verified server quota contract returns subscription and limits alongside
quota. Preserve subscription; entitlement is only an optional compatibility alias.

## Reproducible tests

All network calls in the test suite are fake httpx transports. An autouse fixture
blocks socket connect/connect_ex, so a missing mock cannot consume credits.
The adapter is vendored independently in these three integrations; any future
contract fix must be applied to all copies and their matching contract tests.

## Release-gate fixes

The candidate was rebuilt after the independent WAV/timeout review. Do not upload
an older 0.2.0 archive: compare the rebuilt checksums in VALIDATION.md. Run the
complete tests against source and the actual installed/extracted artifact, including
tests/test_wav_validation.py. RIFF bounds/chunks/padding, PCM 24000 Hz mono16,
block alignment 2, byte rate 48000 and nonempty even data lengths are mandatory.
Malformed audio must produce invalid_audio and preserve recovery identifiers.

Every job must contain a valid requestId. Run tests/test_job_identifiers.py to
verify missing/mismatched ID rejection and case-insensitive UUID matching.
Returned job and request IDs are normalized to canonical lowercase UUIDs.

The entry point now loads the environment-backed Dify configuration once at startup.
Set MAX_REQUEST_TIMEOUT before starting the plugin. The tool caps its requested
deadline at MAX_REQUEST_TIMEOUT minus five seconds; the host must allow more than
five seconds. With the SDK's 300-second host default, the effective tool default
is 295 seconds. For a full 300-second tool budget, use a host limit such as 600.
Configure outer workflow/proxy timeouts consistently; the plugin cannot override
those limits. tests/test_runtime_deadline.py covers 200-second completion,
environment configuration, actual SDK serverless idle handling, and a 180-second
host returning recovery metadata before its response closes.

## Runtime verification

The source and reviewed package each pass 188 tests. Added subprocess tests use
the actual main.py/SDK stdio entrypoint, with only HTTP and the job clock mocked.
The real serverless HTTP entrypoint also passes /health and streamed /invoke:

    .venv/bin/python scripts/check_runtime_serverless.py
    .venv/bin/python scripts/check_runtime_serverless.py --package .artifact-test/release-final

Both commands bind only an ephemeral loopback port; plugin outbound sockets are
blocked. Host 300/tool 295 completes a simulated 200-second job. Host 180/tool 175
returns recovery metadata at simulated 170 seconds. No Docker is required.
These checks do not verify an external Go daemon, Cloud/CE installation, deployed
egress enforcement, or outer workflow/proxy limits. See VALIDATION.md for exact
reviewer permissions and operator configuration still needed.

## Prepared marketplace update

The local dify-marketplace-update checkout has branch
codex/flowspeech-v0.2.0-update based on upstream main
954626f01c93d8e74cad8ef115cc3c901cd89cc0. Its only candidate change is:

    flowspeech/flowspeech/flowspeech-0.2.0.difypkg

SHA-256: ae19e4209a5b9693ca4435df4b0fa8dc3017e4648e6e69743c2452bb0f0c3384

The accepted package is unchanged. Current update rules require exactly one new
.difypkg, with metadata already inside it. PR text is prepared outside that checkout
in scripts/marketplace_update_pr.md. Keep the old package and upstream files intact.
The public version check on 2026-10-26 found 0.1.0 published and 0.2.0 absent.

The coordinator should resolve or explicitly disclose platform-test limitations,
review the PR checklist, refresh upstream/version availability, commit only the
new package, and push the local branch to the authorized fork before opening a
new version-update PR against langgenius/dify-plugins main, referencing merged #3008.
Do not reuse the closed PR. This worker did not commit, push or create a PR.

