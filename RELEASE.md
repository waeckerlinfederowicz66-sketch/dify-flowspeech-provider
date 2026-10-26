# Release 0.2.0

## Current deployed-validation handoff

The current unpublished 0.2.0 candidate is 126197 bytes/17 members, SHA-256:
`5fc5942eac8185e17f4150da74aceeed2a7c08f935f55b93597f1968a12f05f4`.
The coordinator committed it at the existing draft Marketplace binary path in
commit `1024cfe3385e390626e0e4253b23d4c6b9469651`. Shared pins now use that immutable
commit, and the main `dist/flowspeech-0.2.0.difypkg` matches the downloaded bytes.
Only packaged README/PRIVACY changed; eight Python files, manifest, requirements,
icon and all other members remain byte-identical. The old archive is retained
under `.tools/package-archive/` with its full hash in the filename.

The replacement passes 386 source tests and 188 actual-package tests, but its
**deployed CE and remote-debug gates are pending**. Push the reviewed source/pin
commits to trigger both workflows; review the new hash in both retained artifacts
before claiming either gate passed for this candidate. Keep PR 3513 draft pending
the coordinator's final review. Cloud is an explicitly unvalidated limitation,
not an invented absolute prerequisite. No worker public writes were made.

## Historical deployed evidence: previous package

The complete defined **isolated headless CE gate passed** in
[run 40326427753](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40326427753),
exact head 4ff46caacca3abfbe7615f6099009baf6c42ce4e. All nine retained files were
audited: summary.json has ce_passed=true, cloud_passed=false. Artifact ID
12651777580, 24549 bytes, SHA-256:
`497be24f760c90d5326652582dc3ad8af74831cb92190a5001f83c4dfcd3d7a9`.

Actual slow completion: 200.301s with host 300/tool 295. After real daemon restart,
quota-only readiness took 3.103s; host 180/tool 175 returned recovery at 170.257s,
with one submission, 34 polls, no download and no audio. Credentials, malformed
WAV, both negative redirects, safe HTTPS redirect, requested deadline and file
persistence all passed. Every storage hop was free of Authorization/cookies;
all workflow submissions were single attempts, with no forbidden target reached.
Both isolation checks passed with only internal/no-network containers and no
published ports. The package and its eight installed Python files are unchanged.
Three persisted 18044-byte WAV files have the identical SHA-256:
`ef2b9384c28fa5e94babe9397b3c7201393c4fe9b7e4c39c0683a3f944b2e7ad`.

The 112 offline harness checks pass within 300 source tests; the package passes
188 tests. These support but do not replace the actual deployed evidence above.
See VALIDATION.md for every case timing and audit detail. This pass covers only
the pinned CE 1.18.0/daemon 0.6.10-local configuration. Cloud, production services,
browser/UI, external proxies and managed egress policies remain unvalidated.
No paid API was used. Fixture-CA trust and unsigned-package acceptance are test-only.
Marketplace PR [3513](https://github.com/langgenius/dify-plugins/pull/3513) remains
draft pending the coordinator's review of Marketplace comments and Cloud scope.
That run tested the previous 125757-byte package at SHA-256
`ae19e4209a5b9693ca4435df4b0fa8dc3017e4648e6e69743c2452bb0f0c3384`.

The same old package later passed remote-debug run 40336384519 attempt 2,
including zero-leftover cleanup; see scripts/remote_debug/README.md. These
historical passes do not transfer to the current documentation-replacement hash.
The workstation has no container runtime; the deployed pass is from the audited
GitHub-hosted job, not a local simulation. See `scripts/deployed_ce/README.md` for
reproduction commands and the separate Cloud access gate.
Do not expand this gate to paid APIs, external deployments or browser sessions.

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

## Current marketplace candidate

The coordinator updated the original draft PR 3513 with ordinary commit
`1024cfe3385e390626e0e4253b23d4c6b9469651`. Its candidate binary path remains:

    flowspeech/flowspeech/flowspeech-0.2.0.difypkg

SHA-256: 5fc5942eac8185e17f4150da74aceeed2a7c08f935f55b93597f1968a12f05f4

The accepted 0.1.0 package is unchanged. The pending update still contains exactly
one new .difypkg, with metadata already inside it. Local PR text is in
scripts/marketplace_update_pr.md; the coordinator owns the actual PR body/state.

After both new deployed gates pass for this exact hash, the coordinator reviews
remaining requirements and documented limitations before changing PR readiness.
Do not open a duplicate update PR or reuse closed PR 3008. This worker did not
push, publish, change PR state or modify the official website.

