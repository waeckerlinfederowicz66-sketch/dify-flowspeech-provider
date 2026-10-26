# Validation: dify-flowspeech-provider 0.2.0

Date: 2026-10-26. Final release-gate follow-up in an isolated migration checkout.
The release artifact passes 188 tests (previous baseline 94). Current source also
includes 25 offline tests of the new deployed-CE harness, for 213 source tests.
The final archive supersedes all earlier local 0.2.0 candidates and is unchanged.

## Prepared deployed CE gate (not executed)

The first [CI attempt, 40307156979](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40307156979),
was rejected during workflow validation before any jobs or containers started.
The run-page annotation identifies line 23, column 19: the runner context is not
available in job-level env. GATE_STATE is now initialized in the first step using
RUNNER_TEMP and GITHUB_ENV; step-level artifact paths retain their valid context.
The regression executes that step with a temporary path containing spaces.

Pinned actionlint 1.7.7 reproduces the original context error and passes both
corrected workflows (shellcheck and pyflakes integrations disabled). Its Darwin
arm64 archive was checked against the official release checksums before execution:
2693315b9093aeacb4ebd91a993fea54fc215057bf0da2659056b4bc033873db.
The corrected source suite passes 213 tests with the same two SDK warnings.
This repairs workflow admission only; deployed CE and Cloud remain unvalidated.

`.github/workflows/deployed-ce.yml` and `scripts/deployed_ce/` provide one bounded
40-minute GitHub-hosted job. It uses digest-pinned CE 1.18.0, the real 0.6.10-local
Go daemon, PostgreSQL and Redis. It installs the unchanged reviewed package through
CE, validates provider credentials, runs start/tool/end workflows, retrieves the
persisted WAV, and checks real 200-second completion and a 180-second host deadline.
Malformed audio, redirect refusal, credential-free downloads and no resubmission
are checked through the deployed workflow rather than an SDK shim.

All deployed containers are on an internal network, with no published ports.
Dependencies are staged as wheels and installed offline. Fixed API/storage hosts
resolve to an HTTPS fixture; a disposable CA is added only to the isolated
runtime's certifi trust bundle. Installed plugin Python bytes are compared with
the reviewed package. No plugin source or clocks are changed. This trust setup
and test-only acceptance of an unsigned package are explicitly disclosed limits.

Local checks: 212 source tests passed (2.44s), including 24 new offline harness
checks; the unchanged extracted package passed its 188 runtime tests (2.32s).
The development-only harness tests are excluded from that package run.
Byte-compilation and package audit passed. These are not deployed results.
No Docker runtime is installed here and no workflow was pushed or dispatched.
The first real CI run still must verify Compose rendering, startup/migrations,
installation, credentials, workflow routing, persisted output and real deadlines.
See `scripts/deployed_ce/README.md` for coordinator commands and retained evidence.

PR 3513 was verified open and draft. Cloud remains unvalidated: it requires an
authorized installation/workflow workspace plus platform-controlled mock routing
and certificate trust for the fixed HTTPS hostnames. A CE pass does not close this
gate or validate an external reverse proxy, production storage, or other versions.
Keep the PR draft pending actual deployed evidence and explicit handling of the
Cloud limitation. No underlying production service or paid generation was called.

## Commands and results

- Python 3.12.14; dify_plugin 0.10.2, httpx 0.28.1, pytest 8.4.2, pydantic 2.14.1.
- Source: .venv/bin/python -m pytest -q --basetemp=.test-tmp/runtime-release-gate
  -> 188 passed (2.61s), 2 third-party warnings.
- .tools/dify plugin package . -o dist/flowspeech-0.2.0.difypkg -> succeeded.
- Official Dify CLI 0.6.12 SHA-256 reverified before packaging:
  c730a27b118d1342ac5650f99155033110f394f5a6dbf3023689328bf921efb6.
- .venv/bin/python scripts/verify_artifacts.py dist/flowspeech-0.2.0.difypkg
  --extract-dify .artifact-test/release-final -> passed; fresh extraction.
- From .artifact-test/release-final:
  ../../.venv/bin/python -m pytest ../../tests -q -o pythonpath= --basetemp=.test-tmp/runtime-release-gate
  -> 188 passed (2.49s), the same 2 warnings.
- flowspeech_v1, flowspeech_client, runtime_config and tools.text_to_speech import
  origins explicitly verified inside the final extracted artifact, not source.
- Real Dify SDK ToolInvokeMessage and provider/tool schemas validated.
- .venv/bin/python -m pip check -> no broken requirements.
- Warnings are SDK gevent SSL monkey-patch ordering under pytest and SDK Pydantic
  class Config deprecation. Production main imports dify_plugin first.
- git diff --check -> passed.

## Final artifacts

- dist/flowspeech-0.2.0.difypkg: 125757 bytes, 17 members
  SHA-256: ae19e4209a5b9693ca4435df4b0fa8dc3017e4648e6e69743c2452bb0f0c3384

Archive inspection verified version metadata, safe member paths, forbidden
development files, secret patterns and private local path leakage. No matches
or unintended runtime files were found. Final artifact code was tested, not
only source. VALIDATION.md is intentionally excluded from these archives.

## Release-gate coverage

- 37 shared WAV tests cover RIFF length/chunk/padding bounds, PCM tag 1, 24000 Hz,
  mono 16-bit, block alignment 2, byte rate 48000, nonempty even data length,
  duplicate/missing format or data chunks, malformed extensions, ancillary chunks,
  every truncation offset and deadline checks during parsing.
- Malformed audio raises typed invalid_audio, keeps request/job/result recovery
  identifiers and cannot trigger another create or audio retry.
- 31 shared identifier tests require a valid requestId on submission, polling,
  lookup and cancellation; reject mismatches and normalize both expected and
  returned UUIDs before comparison. Successful results always contain requestId.
- Existing coverage includes single/multi input mapping, legacy-option rejection,
  stable idempotency/body retries, every pending and terminal status, result deletion,
  quota/voices, recovery, cancellation, API errors, Retry-After and total deadlines.
- Downloads are bounded and credential-free even with polluted injected clients
  and redirects. API redirects are refused. Slow transport/stream tests verify
  the caller's absolute deadline.
- Socket connect/connect_ex are blocked automatically in every test. HTTP uses
  fake transports; audio fixtures are locally synthesized, never production output.

## Shared adapter

All three source copies and their installed/extracted artifact copies are identical.

- Adapter SHA-256: f1e49e7eb2915eb7e796ab869d364e02c5987de8347b07aafef381b5a5764ade
- tests/test_wav_validation.py SHA-256: 36bd7ebfd01c0ffe389ecd42747abcee74576d24a4e704b15e75fa93721afbcc
- tests/test_job_identifiers.py SHA-256: cd6e76f062472482094cc3c7dfc004b033e58a00250a4c948192b5edd182ff80

The adapter and these tests are stable for reuse in the separately owned SDK.
No SDK or MCP files were changed by this worker.

## Contract verification

The original v1 routes, DTO and WAV storage implementation were reviewed read-only.
The routes normalize UUIDs and every job DTO emits requestId. Audio storage emits
PCM 24000 Hz mono16, block alignment 2 and byte rate 48000. The quota response
contains subscription and limits alongside quota; entitlement is only an optional
compatibility alias, not a required field.

## Safety and limitations

No authenticated production API requests, real credentials, paid generation,
email, commits, pushes, publication or workflow/OIDC changes were made by this
worker. Public homepage/static-asset and Marketplace metadata reads were used
only for release verification. Existing changes were preserved.
No end-to-end production generation or deployed Dify verification is claimed.
A single in-flight HTTP request may finish cleanup after the local caller deadline;
it cannot submit a retry or another recording. Recover accepted jobs with their
original request/job UUID instead of submitting new input.

## Dify host deadline

20 added runtime tests verify that main and the tool share DifyPluginEnv from the
environment instead of a hardcoded 180-second value. The effective tool deadline
is min(requested timeout, MAX_REQUEST_TIMEOUT - 5 seconds). SDK default host 300
therefore gives tool 295; host 600 permits the full default tool 300. Host budgets
at or below 5 seconds are rejected before creating a client.

A real client and real SDK tool messages complete after 40 simulated five-second
polls (200 seconds), producing one WAV and recovery metadata with only one POST.
The actual SDK serverless request reader also stays open until a simulated
200-second response. With host 180, the tool stops before 175 and emits a recovery
error without audio or a second POST. No heartbeat workaround is used.

The rebuilt package includes runtime_config.py. Actual SDK entrypoints and the
intended result hostname are now verified below. Deployment-specific enforcement
still requires platform access; no Cloud/CE installation is claimed.

## Runtime and egress follow-up

Six added tests in tests/test_runtime_entrypoint.py run main.py as a subprocess
through the unmodified SDK local stdio run loop. Registration, routing, credential
validation, real tool execution, WAV chunk serialization and session end all pass.
Only HTTP transport and the job clock are mocked; sockets are blocked in the child.
The successful job completes at simulated 200 seconds and reconstructs 18044 WAV
bytes from three payload chunks plus the end marker. Host 180 yields a recovery
error at simulated 170 seconds with effective deadline 175. Malformed audio and
rejected credential routes also end cleanly; credentials validation calls quota only.

Actual serverless HTTP smoke commands, each with two passing cases:

- .venv/bin/python scripts/check_runtime_serverless.py
- .venv/bin/python scripts/check_runtime_serverless.py --package .artifact-test/release-final

These start the real SDK HTTP server on an ephemeral loopback port. /health
returns 200 OK; /invoke returns streamed WAV/JSON/session-end at simulated 200
seconds with host 300/tool 295. Host 180/tool 175 returns recovery text/session-end
at simulated 170 seconds. Outbound sockets are forbidden in the plugin subprocess.
No Docker, external daemon, real API, credits or remote credentials are used.
Loopback binding required sandbox approval; both commands then passed.

Egress evidence checked on 2026-10-26:

- Scoped inspection read only the allowlisted R2_PUBLIC_DOMAIN setting from
  local development/example configuration: HTTPS static.flowspeech.io, without
  embedded credentials. No credentials or other environment values were printed.
- The [public homepage](https://flowspeech.io/) references 77 distinct URLs on
  static.flowspeech.io, including public demo WAV assets.
- Credential-free HEAD on [a public demo WAV](https://static.flowspeech.io/assets/1.wav)
  returned HTTP 200, Content-Type audio/wav, Content-Length 217530 and no redirect.
  No audio body was downloaded.
- manifest.yaml already declares exactly flowspeech.io and static.flowspeech.io.
  The hostname regression passes against source and the reviewed package.
  No wildcard or additional egress domain was added.

This verifies the intended public storage hostname, not the effective deployed
daemon/proxy policy. A complete admin storage configuration can override the
environment domain. No production database/configuration API was queried.

## Remaining platform access

- To verify deployment enforcement, a reviewer needs a Dify CE or Cloud workspace
  with plugin-install/workflow permissions, plus operator access to the deployed
  plugin daemon or managed-platform timeout and egress policy. Docker is not
  installed locally; the SDK process smoke tests do not install a complete platform.
- The operator must confirm outbound HTTPS/DNS for flowspeech.io and
  static.flowspeech.io (including any actual result redirect hosts), and align
  outer workflow/proxy/daemon limits with the configured plugin deadline.
- To exclude a production storage override without generation, the operator can
  confirm only the effective public R2_PUBLIC_DOMAIN/r2_domain hostname or the
  hostname of an already-issued result URL. Do not disclose keys or full result URLs.
- An on-platform invocation must use an operator-controlled mock/staging setup;
  real production generation still requires separate approval for keys and credits.
- Marketplace CI/review and final submission remain coordinator actions.

## Local marketplace candidate

Contribution rules, submission requirements, review guidelines and the PR template
were read at upstream main 954626f01c93d8e74cad8ef115cc3c901cd89cc0.
CONTRIBUTING.md contains only TODO; README's update rules and
docs/plugin-submission-requirements.md require a single new package file.

- Local checkout: dify-marketplace-update.
- Branch: codex/flowspeech-v0.2.0-update, based exactly on that upstream main commit.
- Fork remote: https://github.com/waeckerlinfederowicz66-sketch/dify-plugins.git.
- Only candidate change: flowspeech/flowspeech/flowspeech-0.2.0.difypkg.
- The 0.1.0 package is preserved; no tracked upstream file was modified.
- Candidate bytes/hash match the reviewed artifact above; audit passed again.
- Public Marketplace metadata returned 0.1.0 HTTP 200/code 0 and 0.2.0
  HTTP 404/code -1 (plugin version not found). Recheck immediately before submission.
- PR metadata is prepared separately in scripts/marketplace_update_pr.md so
  the marketplace change remains exactly one file. No commit, push or PR was made.

## Files in runtime and egress follow-up (6)

- tests/runtime_entrypoint_harness.py
- tests/test_runtime_entrypoint.py
- scripts/check_runtime_serverless.py
- scripts/marketplace_update_pr.md
- VALIDATION.md
- RELEASE.md

Runtime code, manifest, dependencies and the accepted package are unchanged.
The six source/test/report files are excluded by the existing .difyignore rules.

## Files in preceding release-gate fixes (13)

- flowspeech_v1.py
- runtime_config.py
- main.py
- tools/text_to_speech.py
- tools/text_to_speech.yaml
- tests/test_wav_validation.py
- tests/test_job_identifiers.py
- tests/test_runtime_deadline.py
- README.md
- CHANGELOG.md
- RELEASE.md
- VALIDATION.md
- scripts/verify_artifacts.py

Earlier migration files remain in place; this list only describes this release-gate
follow-up. Generated dist/, test outputs, environments and artifact extractions
are ignored build outputs. See RELEASE.md for coordinator-only release steps.
Confirm registry version availability and upload only the reviewed final hashes.
