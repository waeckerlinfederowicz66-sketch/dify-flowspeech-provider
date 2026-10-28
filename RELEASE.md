# FlowSpeech 0.2.1 Final Package Acceptance

Package: `dist/docs-r1/flowspeech-0.2.1.difypkg`,127641 bytes,17 members.
SHA-256 `523701c995e653e66fdc357077a13bc1ce337a115efe54e371975046857284f2`.
DOC `6a5d4dd422e0c378ec63c0c7f5661b35f6905064`; tested PIN `2c4d84437f378e82c03531e171bbdb30e4ff2e59`.
Both independent exact-payload builds passed before Docker:
[remote-debug](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40639776746) and [CE](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40639803640); downloaded artifact digests,
member/runtime identity, actual cases and cleanup were independently checked.
Source CI passed585 tests; fresh local focused322/extracted293/4SDK loopback
cases passed. Only public README/CHANGELOG changed from the protected15 members.

These are PIN CI results, not CI for any later excluded-docs-only commit.
Original QA refs/draft/assets and old packages remain preserved. Source/default
updates,formal release and a new0.2.1 Marketplace PR need separate parent review
of the publication bodies and this docs-only diff; none is implied by this file.
No Cloud/browser/UI/production API or external-proxy trust/egress pass is claimed.
Remote cleanup proved zero resources/credential removal; CE Compose cleanup
succeeded with remaining fixture state owned by the ephemeral runner.

Historical sections below are preserved as dated evidence, not current
instructions or publication claims. Earlier PR/status/hash statements are
superseded by the verified 2026-10-28 snapshot: PRs #3008 and #3513 merged.

## Historical Release 0.2.0 Evidence

Everything below records earlier artifacts only, not the 0.2.1 release candidate.

## Local Transport Review Candidate - Not Published

The final local candidate now also includes diagnostic privacy hardening:
`dist/transport-privacy-review-candidate/flowspeech-0.2.0.difypkg`, 127962 bytes,
17 members, SHA-256
`86ecb76eafd9f93497ea3254e79cd65924b63ccbb2ab1b620bdb5e1cefddc608`.
Source tests: 491 passed. Extracted-package tests: 293 passed. The adapter SHA-256
is `ef930ce515ad28c5efeb54b7fb07d4ec983131d2771c2c8a948bb93b95b903f6`.
This supersedes the transport-only local candidate below, not the submitted
Marketplace archive. Independent review must use this new hash. No deployed
CE/remote-debug pass is claimed for either local correction candidate.

### Earlier Transport-Only Candidate

2026-10-27: source now contains unreleased response-body/close retry-policy and
bounded-worker corrections. Version metadata remains 0.2.0 by instruction. The
new local artifact is `dist/transport-review-candidate/flowspeech-0.2.0.difypkg`,
127660 bytes, 17 members, SHA-256:
`44b34622f59be71514e364ad133967d36eb13a5f7420f8edf7482fe88e06c254`.
It passes 461 source tests and 263 extracted-package tests, including 75 new
transport regressions. See the first section of VALIDATION.md for commands and
limitations. It has not been tested in deployed CE/remote-debug or published.

The existing main dist archive, Marketplace submission and deployment pins are
unchanged. They still identify `5fc5942e...12f05f4` and do NOT contain these fixes.
The deployed evidence below applies only to that old artifact. The coordinator
must independently review this delta, determine the publishable version, and
refresh candidate/pins and deployment gates before any replacement submission.
No commit, push, publish, production request or ROOT status update was performed.

## Historical Deployed-Validation Handoff

The previously submitted 0.2.0 candidate is 126197 bytes/17 members, SHA-256:
`5fc5942eac8185e17f4150da74aceeed2a7c08f935f55b93597f1968a12f05f4`.
The coordinator committed it at the existing draft Marketplace binary path in
commit `1024cfe3385e390626e0e4253b23d4c6b9469651`. Shared pins now use that immutable
commit, and the main `dist/flowspeech-0.2.0.difypkg` matches the downloaded bytes.
Only packaged README/PRIVACY changed; eight Python files, manifest, requirements,
icon and all other members remain byte-identical. The old archive is retained
under `.tools/package-archive/` with its full hash in the filename.

The replacement passes 386 source tests, 188 actual-package tests, actionlint and
artifact audit. **Both deployed gates passed for this exact hash** at head
`f86c9e173582845b7766795666c12c9d2b3b52db`:

- Full CE [run 40341320875](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40341320875),
  artifact 12660501086, 24555 bytes, SHA-256
  `4eb66282c5a6f381bbafc797615419f372b2c8d548bc42248cc67d2c6d29dae0`.
- Official remote-debug [run 40341321010](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40341321010),
  artifact 12659540576, 26377 bytes, SHA-256
  `7d2b136d6ee6581c337b54229e4aac548dccf17fe265023620415cf2a3a2e664`.

Both archives and all retained reports were independently audited against the
current package/pins and eight Python files. CE slow completion took 200.384s;
host 180/tool 175 returned recovery in 170.335s after a separate 3.138s readiness
probe, with one submission, 34 polls and no audio. Credentials, malformed WAV,
both rejected redirects, safe redirect, requested deadline and persistence passed.
Remote registration/dispatch completed a workflow in 17.368s; disconnect then
rejected that same draft in 0.126s with zero API/storage calls and no fallback.
Every storage hop was credential/cookie-free; four persisted WAVs share SHA-256
`ef2b9384c28fa5e94babe9397b3c7201393c4fe9b7e4c39c0683a3f944b2e7ad`.
All deployment isolation checks passed. CE logs confirm removal of seven
containers, one network and three volumes; remote cleanup confirms zero remaining
containers/networks/volumes and removal of ephemeral secret files.

Final summaries are `ce_passed=true`, `remote_debug_passed=true` and
`cloud_passed=false`. See VALIDATION.md for every case, exact retained evidence
and scope. Cloud, browser/UI, production services and managed egress policies
remain unvalidated; no paid API was used. Cloud is a documented limitation, not
an unconditional prerequisite. Keep PR 3513 draft pending the coordinator's final
review. This result-only update changes VALIDATION/RELEASE, not path-filtered
harness READMEs, runtime, package, pins or workflows. No worker public writes
were made; the coordinator owns push and PR readiness.

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
3. Preserve the exact validated archive and immutable pin above; no repack is
   needed for this documentation-only result update.
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
3513, referencing the merged original. Both defined headless deployment gates
are now passed for the current candidate; final Marketplace review remains open.

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

Both new deployed gates passed for this exact hash. The coordinator reviews their
retained evidence, remaining requirements and documented limitations before
changing PR readiness.
Do not open a duplicate update PR or reuse closed PR 3008. This worker did not
push, publish, change PR state or modify the official website.

