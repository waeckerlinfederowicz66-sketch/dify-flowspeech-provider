# Validation: dify-flowspeech-provider 0.2.0

Date: 2026-10-26. Final release-gate follow-up in an isolated migration checkout.
The release artifact passes 188 tests (previous baseline 94). Current source also
includes 112 offline tests of the deployed-CE harness, for 300 source tests.
The final archive supersedes all earlier local 0.2.0 candidates and is unchanged.

## Deployed CE gate passed (isolated headless CE only)

[CI run 40326427753](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40326427753)
completed successfully at exact head 4ff46caacca3abfbe7615f6099009baf6c42ce4e.
Every job step passed, including daemon restart, short-host validation, redacted
evidence collection and project/volume cleanup. All nine retained evidence files
were audited. summary.json reports **ce_passed=true, cloud_passed=false**, with
isolation, install, run and short-host each passed.

Evidence archive: dify-ce-validation-40326427753, artifact ID 12651777580,
24549 bytes. Verified SHA-256:
497be24f760c90d5326652582dc3ad8af74831cb92190a5001f83c4dfcd3d7a9.
The archive contains only install.json, isolation.json, package-audit.json,
pins.json, run.json, runtime-identity.json, service-logs.txt, short-host.json and
summary.json. The retained pins match the repository exactly: CE 1.18.0 and
daemon 0.6.10-local, with digest-pinned images and 36 recorded wheel hashes.

| Case | Actual elapsed | Creates / polls / downloads | Verified result |
| --- | --- | --- | --- |
| Provider credentials | not timed | quota-only validation | Invalid rejected; valid saved |
| Basic | 18.405s | 1 / 1 / 1 | One persisted WAV and recovery IDs |
| Slow, host 300/tool 295 | 200.301s | 1 / 40 / 1 | One persisted WAV and recovery IDs |
| Malformed WAV | 5.108s | 1 / 1 / 1 | Recovery IDs; no audio output |
| API redirect | 0.102s | 1 / 0 / 0 | Rejected; forbidden target not reached |
| Unsafe audio redirect | 5.122s | 1 / 1 / 1 | Rejected; forbidden target not reached |
| Safe HTTPS audio redirect | 5.148s | 1 / 1 / 2 | Both hops credential-free; one WAV |
| Requested timeout 10s | 5.105s | 1 / 1 / 0 | Recovery IDs before deadline; no audio |
| Post-restart readiness | 3.103s | 0 creates; 1 quota GET | Invalid rejected on attempt 2 |
| Host 180/tool 175 | 170.257s | 1 / 34 / 0 | Recovery IDs before both limits; no audio |

The 180-second case requested 300 seconds against a job delayed 200 seconds.
Daemon recreation with GATE_HOST_TIMEOUT=180 is recorded in the CI log. Runtime
readiness occurs before, and is excluded from, the measured workflow interval.
The observed 170.257 seconds is below the unchanged 175-second tool cap and
180-second host response limit, with no retry or second submission. Returning
before the next five-second poll would exceed the deadline is expected behavior.

Basic, slow and safe-redirect each persisted exactly one 18044-byte PCM WAV.
The driver downloaded all three through CE's file service, compared every byte
with the fixture, and retained each computed SHA-256. All three equal:
ef2b9384c28fa5e94babe9397b3c7201393c4fe9b7e4c39c0683a3f944b2e7ad.
The installed package is 125757 bytes/17 members, SHA-256:
ae19e4209a5b9693ca4435df4b0fa8dc3017e4648e6e69743c2452bb0f0c3384.
All eight installed Python files match the archive; plugin_code_changed=false.

Security/network audit: every workflow has exactly one submission attempt; all
storage hops, including the cross-host redirect, have authorization_present=false
and cookie_present=false. No forbidden redirect target was requested. Slow-job
minimum poll interval is 5.003937s; short-host minimum is 5.004033s. Startup and
post-restart isolation checks both passed. The seven persistent containers use
only the job-scoped internal network, except init-storage in network mode none.
Compose also places the ephemeral driver only on that internal network. No host
ports, privileged containers or Docker sockets are exposed. Fixed API/storage
hostnames resolve to the internal HTTPS mock; images/wheels are staged before
deployment, so this does not claim the entire GitHub runner is offline.

Service-log startup errors correspond to the first readiness probe; the next
probe reaches quota and rejects the invalid fixture credential. This was followed
by the successful single deadline workflow. Sanitized diagnostics were collected
successfully and the job network and all three volumes were removed. Settings,
credentials, private CA keys and database contents are not in the artifact.

**Scope:** the complete defined gate passed on this disposable, headless CE
configuration with the real API, worker, Go daemon and unchanged package. Dify
Cloud, production generation/storage, browser/UI, external reverse proxies,
other versions and managed egress policies remain unvalidated. No paid API was
used. The fixture CA and test-only unsigned-package acceptance do not prove
production trust or Marketplace signature acceptance. PR 3513 remains draft;
the coordinator owns review of Marketplace comments and the unresolved Cloud
scope. No PR state, public comment, push or publication was performed here.

Post-audit local checks: 300 source tests passed (2.53s), extracted original package
188 passed (2.27s), with the same two SDK warnings. Both workflows pass actionlint
1.7.7; package audit and git diff checks pass. This update changes documentation
only, not the tested harness, runtime source or reviewed package.

### Previous daemon-readiness failure

[CI run 40323882509](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40323882509)
ran exact head 23da25ba8ac71a94c5cec3c775cec1765a6e69ae. Isolation, real installation
and the entire main workflow stage passed. The 180-second host stage failed just
after daemon recreation, before measuring the intended long-running job.

Sanitized artifact ID 12649854921, 26236 bytes, verified SHA-256:
6275ddf7d65f6d13c0eb05a04e912fc3dd81dd98d318b9432a48a0fbbcfafa4b.
Package audit matches the unchanged 125757-byte final archive; all eight installed
Python files match. The summary reports run=passed, short-host=failed and both
ce_passed/cloud_passed=false. Audited main-stage evidence:

| Case | Real elapsed | Creates / polls / downloads | Result |
| --- | --- | --- | --- |
| Provider credentials | not timed | quota-only validation | Invalid rejected; valid saved |
| Basic | 23.529s | 1 / 1 / 1 | One persisted WAV |
| Slow | 200.382s | 1 / 40 / 1 | One persisted WAV, host 300/tool 295 |
| Malformed WAV | 5.145s | 1 / 1 / 1 | Recovery IDs, no audio |
| API redirect | 0.136s | 1 / 0 / 0 | Refused; no target request |
| Unsafe audio redirect | 5.138s | 1 / 1 / 1 | Refused; no target request |
| Safe HTTPS audio redirect | 5.153s | 1 / 1 / 2 | One WAV, both hops credential-free |
| Requested timeout 10s | 5.130s | 1 / 1 / 0 | Recovery IDs before deadline, no audio |

All three persisted-file hashes are recorded in run.json and equal:
ef2b9384c28fa5e94babe9397b3c7201393c4fe9b7e4c39c0683a3f944b2e7ad.
The driver downloaded each file through CE and checked exact fixture bytes.
All completed cases have one submission, no forbidden redirect target and no
Authorization/cookies on any storage hop. Slow-job minimum poll interval:
5.004944s. No second recording or live production request was used.

Short-host failure is a startup race, not a measured timeout failure. Daemon logs
show local runtime startup at 12:42:55.103 UTC, metadata requests returning 200,
then dispatch at 12:42:55.569 failing with "no available node, plugin runtime not
found". /tools and /info expose installed metadata, not an available process.
The workflow failed before any long-running job could validate host 180/tool 175.

The driver now waits up to 90 seconds for actual post-restart dispatch before
starting the measured workflow. It sends deliberately invalid fixture credentials
through the existing CE validation route; readiness requires INVALID_API_KEY plus
observed quota-only requests and zero jobs. Only the specific runtime-not-found
startup response is retried. Invalid-credential acceptance, unrelated auth/TLS/
redirect errors, malformed responses or any audio creation fail the gate. Probe
requests are bounded to at most 10 seconds each. There is no generation retry,
blind sleep or metadata-only substitute, and credentials are not added again.
Readiness results are separate from the unchanged 160 <= elapsed < 180 assertion;
the plugin's 175-second cap and all host/network configuration remain unchanged.

Current local results: 112 harness tests passed (0.15s), 300 source tests passed
(2.48s), unchanged extracted package 188 passed (2.19s), with the same two SDK
warnings in full/runtime suites. Eighteen new regressions cover startup retries,
deadline exhaustion, quota-only proof, auth denial, unexpected HTTP/TLS/redirect
errors and ordering before the sole measured generation. Both workflows pass
actionlint 1.7.7, package audit and git diff checks passed. At that handoff the fix
still needed CI; the later successful run is recorded above. Cloud remains unvalidated.

### Previous redirect-fixture failure

[CI run 40312866581](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40312866581)
on commit 04babce passed isolation, real daemon installation and credential
validation, then completed four workflow cases before a fixture assertion failed.
The exact package SHA-256 matches the final artifact below, and all eight installed
plugin Python files match the reviewed archive. No plugin code was changed.

The sanitized artifact (ID 12645244483, 25919 bytes) was downloaded and verified:
SHA-256 ccc1e229d72769662a5f119beda123163662c4e11875eb7a9103f0fcdd5c2bb2.
Its summary remains ce_passed=false and cloud_passed=false; isolation and install
passed, run failed and short-host did not run. Audited completed results:

| Case | Real elapsed | Creates / polls / downloads | Result |
| --- | --- | --- | --- |
| Provider credentials | not timed | quota-only validation | Invalid rejected; valid saved |
| Basic | 21.840s | 1 / 1 / 1 | One persisted WAV and recovery metadata |
| Slow | 200.407s | 1 / 40 / 1 | One persisted WAV, host 300/tool 295 |
| Malformed WAV | 5.164s | 1 / 1 / 1 | Recovery error, no audio output |
| API redirect | 0.154s | 1 / 0 / 0 | No redirect follow or audio output |

Completed-case audits contain no storage Authorization or cookies, no second
submission and no forbidden target. The slow case's minimum poll interval is
5.005322s. Successful audio cases are recorded only after downloading from CE's
file service and comparing every byte with the 18044-byte fixture. That fixture's
SHA-256 is ef2b9384c28fa5e94babe9397b3c7201393c4fe9b7e4c39c0683a3f944b2e7ad;
this run did not retain the separately calculated persisted-file hash.

Failure: audio-redirect reported "A redirect was followed". The fixture had sent
a valid HTTPS redirect, but the harness expected all audio redirects to fail.
The unchanged adapter and public README explicitly support credential-free HTTPS
audio redirects while refusing API redirects and unsafe audio URLs. The wrong
fixture expectation is not evidence of an adapter regression. The failed case's
audit was not retained, so its credential behavior is not independently claimed.

The negative fixture now redirects to an unsafe URL with userinfo, preserving the
no-forbidden-target, no-audio and recovery-ID assertions. A new positive
audio-redirect-safe case follows HTTPS between the two already-isolated hosts,
requires exactly two credential-free download hops, one submission, matching
recovery IDs and the exact persisted WAV. It does not bypass any negative case.
Persisted audio SHA-256 and failed-case mock audits will now be retained. The
production adapter, package, host time limits and Compose isolation are unchanged.

Current local checks: 94 harness tests passed (0.16s), 282 source tests passed
(2.43s), and the unchanged extracted package passed 188 tests (2.36s). Full and
package suites retain the same two SDK warnings. Both workflows pass actionlint
1.7.7 and the package audit passes. Eleven new regressions exercise the actual
adapter against the fixture, reject credentials at the redirect destination,
and prove the driver still rejects forbidden targets, credential leaks, extra
hops and persisted-byte mismatches.

Next deployed run must pass both audio-redirect cases, the short requested
deadline and the actual 180-second daemon stage. The latter two were not reached
in this run. This is partial headless CE evidence only, not a complete CE pass or
Cloud, browser/UI, reverse-proxy or production-storage validation.

### Previous credential-readiness failure

[CI run 40310456564](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40310456564)
on commit b60394d passed isolation and installed the exact package through CE and
the real local Go daemon. The installed runtime matched all eight plugin Python
files; plugin_code_changed is false. The workflow stage failed before any test
case or credential validation: results is empty and current_case is null.

The sanitized artifact (ID 12644437082, 14876 bytes) was downloaded and verified:
SHA-256 065bcc3e2a9b76a3a27a56adf33a7a0a82f8fdc86271821bdea4abb2026f540b.
Its summary reports isolation=passed, install=passed, run=failed and
short-host=not_run. The run error is a 120-second readiness timeout. API logs show
repeated GET /info returning 400 with "you have not added provider", while the
daemon successfully returned installed tool metadata (HTTP 200).

The pinned [CE service contract](https://github.com/langgenius/dify/blob/50abea97062110044f15d0e03ccecadd9ccc87ca/api/services/tools/builtin_tools_manage_service.py#L111)
requires saved provider credentials for /info; /tools requires only the installed
provider. The driver incorrectly waited on /info before calling /add, so no wait
duration could make the fresh instance ready. This is a driver ordering defect,
not evidence of a plugin invocation or 200-second completion failure.

The driver now checks the exact installed tool name through /tools, rejects invalid
credentials, saves valid credentials, then checks /info and /tools before running
the unchanged cases. The short-host stage still requires existing saved credentials
and does not add them again. Permanent 4xx and redirects propagate immediately
instead of becoming readiness timeouts; transient statuses retain bounded retries.
Provider substage names are retained in sanitized failure evidence. No assertion,
workflow case, timeout bound, network restriction or runtime package was removed.

Current local results:

- .venv/bin/python -m pytest tests/test_deployed_ce_gate.py -q: 83 passed (0.10s).
- .venv/bin/python -m pytest -q: 271 passed (2.37s), 2 existing SDK warnings.
- Extracted reviewed package, excluding development-only harness tests:
  188 passed (2.29s), the same 2 warnings.
- Both workflows pass actionlint 1.7.7; package audit and unchanged SHA-256 pass.

The 21 new regressions reproduce CE's saved-credential prerequisite, verify the
request order and exact tool identity, preserve invalid-credential rejection and
all six cases including real-time bounds, require saved credentials on short-host,
and verify permanent-error propagation and transient retry/deadline behavior.
These are offline harness tests, not deployed workflow results. The next CI run
must still validate credentials, workflow execution, persisted output and both
real-time waits. Cloud remains unvalidated.

### Previous startup-guard failure

[CI run 40308695432](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40308695432)
on commit 883ae06 started the real containers. PostgreSQL and Redis became healthy,
the API completed migrations and became healthy at 10:38:05 UTC, and the worker
started. The startup step then failed in check_isolation.py at its network-name
allowlist assertion, not in Compose startup. Install, run and short-host were
skipped; the retained summary correctly reports CE and Cloud as unvalidated.

The sanitized artifact (ID 12643706380, 11041 bytes) was downloaded and verified:
SHA-256 8bbeed8e5419708f5b9404b21eaa5108d578fab7722ff61fde35ca976be04779.
It contains package-audit.json, pins.json, service-logs.txt and summary.json.
The old guard wrote isolation evidence only on success, so this run does not
identify the offending container. The Compose init-storage service has network
mode none; Docker's none network entry reproduces the failing assertion offline.
This is the identified guard defect, not a claim that raw runtime inspect data
was retained. Docker documents that [none provides only loopback](https://docs.docker.com/engine/network/drivers/none/).

The guard now accepts an empty network map or the none entry only for network
mode none, with no IPv4/IPv6 addresses, gateways or prefixes. Other containers
must use exactly the inspected project-internal network. Host/bridge/shared
network modes, extra attachments, published ports, privileged containers and the
Docker socket remain rejected. Compose, image pins and network isolation are
unchanged. Failure evidence now records service, mode and network names without
environment variables; the summary requires isolation plus all three deployed
stages to pass. No installation or workflow pass is inferred from local tests.

Local revalidation after this fix:

- .venv/bin/python -m pytest tests/test_deployed_ce_gate.py -q: 62 passed (0.10s).
- .venv/bin/python -m pytest -q: 250 passed (3.31s), 2 existing SDK warnings.
- Extracted reviewed package, excluding development-only harness tests:
  188 passed (2.53s), the same 2 warnings.
- Both workflows pass actionlint 1.7.7; package audit and unchanged SHA-256 pass.

The 37 new regressions cover Docker none representations, routed and extra
attachments, unsafe network modes, host protections, failure-evidence retention,
secret-free inspect summaries and fail-closed result aggregation.

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
That earlier correction passed 213 source tests and repaired workflow admission
only; it did not establish a deployed CE or Cloud pass.

`.github/workflows/deployed-ce.yml` and `scripts/deployed_ce/` provide one bounded
40-minute GitHub-hosted job. It uses digest-pinned CE 1.18.0, the real 0.6.10-local
Go daemon, PostgreSQL and Redis. It installs the unchanged reviewed package through
CE, validates provider credentials, runs start/tool/end workflows, retrieves the
persisted WAV, and checks real 200-second completion and a 180-second host deadline.
Malformed audio, API/unsafe-audio redirect refusal, credential-free downloads and no resubmission
are checked through the deployed workflow rather than an SDK shim.

All deployed containers use an internal network or no network, with no published ports.
Dependencies are staged as wheels and installed offline. Fixed API/storage hosts
resolve to an HTTPS fixture; a disposable CA is added only to the isolated
runtime's certifi trust bundle. Installed plugin Python bytes are compared with
the reviewed package. No plugin source or clocks are changed. This trust setup
and test-only acceptance of an unsigned package are explicitly disclosed limits.

No Docker runtime is installed here and this worker did not push or dispatch CI.
Subsequent runs resolved these integration failures; the complete defined CE gate
passed in run 40326427753 as recorded above. Cloud is still outside that evidence.
See `scripts/deployed_ce/README.md` for coordinator commands and retained evidence.

PR 3513 was verified open and draft. Cloud remains unvalidated: it requires an
authorized installation/workflow workspace plus platform-controlled mock routing
and certificate trust for the fixed HTTPS hostnames. A CE pass does not close this
gate or validate an external reverse proxy, production storage, or other versions.
Keep the PR draft pending coordinator review of the deployed CE evidence and
explicit handling of the Cloud limitation. No production service or paid generation was called.

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
email, pushes or publication were made by this worker. Validation changes are
committed locally for coordinator review; no OIDC or authentication changes were
made. Public asset, Marketplace and CI reads were used for release verification.
Existing changes were preserved.
No production generation, Cloud or browser validation is claimed. The complete
defined CE gate pass is limited to the isolated configuration and cases above.
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
intended result hostname are verified below. These SDK-only checks did not establish
installation; the later complete defined CE gate evidence is recorded above.

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

- Beyond the isolated CI configuration, a reviewer needs a Dify CE or Cloud workspace
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
