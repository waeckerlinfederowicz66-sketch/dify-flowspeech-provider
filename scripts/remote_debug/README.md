# Supplemental Remote-Debug Gate

This independent, bounded CI job tests Dify's official TCP remote-debug protocol.
It does not replace or modify the passed full CE gate (run `40326427753`, head
`4ff46caacca3abfbe7615f6099009baf6c42ce4e`). **The supplemental gate passed in run
40336384519 attempt 2 for the exact package hash below, including cleanup.**
This technical result is not Marketplace approval or a claim that a different
replacement package has passed deployed validation.

## Official Contract

- [Plugin debugging](https://docs.dify.ai/en/develop-plugin/features-and-specs/plugin-types/remote-debug-a-plugin):
  obtain a workspace debugging key, set `INSTALL_METHOD=remote` and
  `REMOTE_INSTALL_URL=host:port`, then run `python -m main`.
- [Publishing guidelines](https://docs.dify.ai/en/develop-plugin/publishing/standards/contributor-covenant-code-of-conduct):
  the end-to-end criterion explicitly calls for remote debugging. Installing a
  package into the local Go daemon alone does not establish this protocol.
- [CE debugging-key route, pinned source](https://github.com/langgenius/dify/blob/50abea97062110044f15d0e03ccecadd9ccc87ca/api/controllers/console/workspace/plugin.py):
  authenticated owner `GET /console/api/workspaces/current/plugin/debugging-key`.
- [Daemon registration lifecycle, pinned source](https://github.com/langgenius/dify-plugin-daemon/blob/1310a18b2f6bc6f18768a0a6265484830891433c/internal/service/install_service/controlpanel.go):
  a connected runtime creates a `remote` installation; disconnect removes it.
- [Daemon TCP handshake, pinned source](https://github.com/langgenius/dify-plugin-daemon/blob/1310a18b2f6bc6f18768a0a6265484830891433c/internal/core/debugging_runtime/hooks.go):
  workspace-key handshake, manifest/tool/assets transfer, initialization end.
  The fixture explicitly sets the connection limit to 2; a zero limit rejects
  every completed handshake in this pinned version.

The [Marketplace PR template](https://github.com/langgenius/dify-plugins/blob/main/.github/pull_request_template.md)
allows CE/Cloud testing **or documented limitations**. This gate does not infer an
absolute Cloud requirement. Cloud, browser/UI, production requests and public
egress-policy validation remain untested. Marketplace readiness and policy review
are separate from the technical result; no submission state is changed here.

## Exact Candidate and Isolation

Reuse `scripts/deployed_ce/pins.json`: CE 1.18.0, Go daemon 0.6.10-local, Python
3.12.14, and all five Docker images by digest. The immutable package is
`flowspeech-0.2.0.difypkg`, 125757 bytes, SHA-256:

`ae19e4209a5b9693ca4435df4b0fa8dc3017e4648e6e69743c2452bb0f0c3384`

All 17 members, including all eight Python files, are compared byte-for-byte
before execution; per-Python-file hashes are retained. During a gate run no plugin
code, manifest, requirements, package or original entrypoint is changed or repackaged. The
extracted package is mounted read-only, bytecode writing is disabled, and the
launcher execs the original `python -m main` with an allowlisted environment.

The 30-minute job creates a unique fresh CE project. No installed package is
uploaded, and the daemon cannot access the candidate or its Python source.
The driver forbids upload/install routes and rejects any local/serverless
installation. All services use one `internal: true` network; debug TCP 5003 has
no host mapping. Runtime dependency installation uses `network_mode: none`.
Images and binary wheels are staged before isolation; dependency wheel hashes
are retained. The dependency lock scope is unchanged from the full CE gate:
direct SDK/HTTP client versions are pinned, transitive wheel versions/hashes are
recorded per run.

Only the disposable remote venv's certifi bundle gains the fixture CA. Both
public API/storage hostnames resolve to the internal mock. No production API,
real subscription, paid generation, cloud deployment or repository secret is
used. The ephemeral workspace key lives only in private job state and process
environment; it is never a shell argument, printed response or uploaded file.
Redaction includes that exact key. Cleanup removes all project containers,
networks and volumes, verifies zero leftovers, then deletes private credential
and CA-key files even when evidence validation fails.

## Required Evidence

1. Fresh workspace with zero plugins; official debugging-key API succeeds.
2. Exactly one FlowSpeech 0.2.0 installation with `runtime_type=remote`.
3. Invalid credentials rejected through actual remote quota dispatch; valid
   credentials validated and saved, with only authenticated quota GETs.
4. One real CE workflow succeeds: exactly one job POST, queued polling, one
   credential-free/cookie-free storage download, and one persisted WAV retrieved
   from CE's own file endpoint. Its expected SHA-256 is
   `ef2b9384c28fa5e94babe9397b3c7201393c4fe9b7e4c39c0683a3f944b2e7ad`.
5. Stop the remote container. Wait for registration removal, then invoke the
   same successful draft once. Require an explicit unavailable-plugin error,
   zero API/storage calls, zero jobs and no fallback installation. Unrelated
   auth/TLS/HTTP errors, missing terminal events and success cannot pass.
6. Both live isolation checks, exact runtime identity and cleanup must pass.
   `summary.json` must say `remote_debug_passed: true`, `cloud_passed: false`.
   It deliberately does not overwrite or reinterpret the separate `ce_passed`.

Only the allowlisted `evidence/` directory is uploaded for seven days. JSON
containing any fixture/debugging credential, JWT, certificate or unexpected file
blocks upload. Logs are bounded and redacted before the same leak check. Raw
console responses, cookies, `.env`, private keys and workspace debugging keys
are never retained as evidence.

## Coordinator Handoff

Review the local commit, then push `codex/public-api-v1`. The workflow's path
filter covers its own harness, the shared CE harness/pins and artifact verifier.
A change to shared CE harness/pins can trigger both deployed gates. A manual
alternative after push is:

```sh
gh workflow run remote-debug.yml --ref codex/public-api-v1
```

The job needs only standard GitHub-hosted Ubuntu Docker/Compose, internet for
initial pinned assets/wheels, and no repository/environment secrets. It cannot
be executed locally here because no Docker engine is available. Download the
`dify-remote-debug-<run-id>` artifact after the run and audit all stage statuses,
package/eight-file hashes, registration type, persisted audio hash, download
header flags, disconnect result and cleanup evidence before updating any
Marketplace checkbox. A green ordinary unit-test workflow is not sufficient.

Local checks:

```sh
.venv/bin/python -m pytest tests/test_remote_debug_gate.py -q
.venv/bin/python -m pytest -q
.tools/actionlint-1.7.7/actionlint -shellcheck= -pyflakes= .github/workflows/remote-debug.yml .github/workflows/deployed-ce.yml
.venv/bin/python scripts/verify_artifacts.py dist/flowspeech-0.2.0.difypkg
```

Run artifact-only tests in the existing extracted package directory with both
development harness test files excluded. Do not overwrite the pinned reviewed package.

## Local Candidate Validation

The candidate preparation checks passed on Python 3.12.14: 84 supplemental-gate
tests, 384 total source tests, and 188 tests against the unchanged extracted
release package. Source/artifact suites retain the two existing SDK warnings
(gevent SSL import order and deprecated Pydantic class configuration).
Actionlint 1.7.7 passed all three workflows. The artifact audit and a fresh
extraction verified all 17 members and eight Python-file hashes.

Ignored local review evidence is under `.tools/remote-debug-candidate/`:
`source-tests.xml`, `artifact-tests.xml`, and `package-identity.json`.
This machine has no Docker engine. No public push, workflow dispatch or
Marketplace state change was made by the implementation worker.

## First Deployed Attempt

[Run 40334275182](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40334275182)
tested head `9e3fa43342e34fec7f13acf83dedb945aac0082e`. Both isolation checks,
fresh workspace bootstrap, immutable runtime identity, actual remote credential
dispatch, the full workflow and the disconnect negative test passed. The overall
job failed its zero-leftover cleanup guard, so that run's `remote_debug_passed`
remains **false**; no Marketplace readiness is inferred.

The invalid quota probe was rejected in 0.141 seconds (one GET, zero creates),
and the valid credential save made one quota GET. The workflow succeeded in
22.457 seconds with exactly one POST, one poll and one storage download, without
storage authorization or cookies. The persisted WAV matched the hash above.
After stopping the remote process, the same draft failed explicitly because its
plugin was unavailable in 0.169 seconds: zero API/storage calls, zero creates,
and zero remaining plugin installations. Runtime type was `remote`; all 17
package members and eight Python hashes matched. The ephemeral credential files
were removed. Cloud remains unvalidated.

The retained artifact is `dify-remote-debug-40334275182` (ID `12656281757`,
26135 bytes), SHA-256
`c367f65c75ee32b94e1af8ded17cd582d4598dfd96c42e60f5425db44ae7882b`.
Its 11 files are retained locally under
`.tools/remote-debug-run-40334275182/evidence/`, beside `diagnostics.zip`.

Cleanup returned successfully from Compose but failed at the first container
inventory check; the original report did not retain container names or counts.
The command omitted `--profile validation`, although `remote_plugin` is a
declared profile service. [Compose's profile lifecycle](https://docs.docker.com/compose/how-tos/profiles/)
requires enabling that profile for `down`; declared inactive-profile services
are not orphans. The focused harness correction enables `validation` for
collection and cleanup, preserving the zero-container/network/volume guard and
retaining all three counts on failure. It also includes the remote client's
logs in the existing secret-redaction path. The subsequent full result is
recorded below; this first run remains an overall failure.

The focused cleanup revision passed 86 supplemental tests, 386 total source
tests, 188 unchanged-package tests, all three workflow actionlint checks, and
the artifact audit. Its local XML reports are
`.tools/remote-debug-run-40334275182/fix-source-tests.xml` and
`fix-artifact-tests.xml`. Existing full CE/runtime code and release-package
bytes were unchanged. These offline checks alone did not establish a successful
cleanup on a real Docker host.

## Successful Remote Deployment

[Run 40336384519, attempt 2](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40336384519/attempts/2)
completed successfully at head `1845dbb858357159328c87c20bbfdc00c62da37a`, job
`121621365701`. Attempt 1 stopped before deployment because Docker Hub returned
HTTP 500 for the pinned CE image manifest; dependencies and assertions were not
relaxed for the coordinator's bounded retry.

All seven retained stage reports passed. The invalid quota probe was rejected
in 0.132 seconds (one GET, zero creates); valid credential save made one quota
GET. The real remote workflow completed in 20.903 seconds with exactly one job
POST, one status poll and one storage download. Storage received neither API
authorization nor cookies. CE's persisted WAV matched
`ef2b9384c28fa5e94babe9397b3c7201393c4fe9b7e4c39c0683a3f944b2e7ad`.

After stopping the remote container, the same successful draft failed explicitly
with an unavailable-plugin error in 0.149 seconds. There were zero API/storage
calls, zero creates and zero remaining plugin installations. The daemon reported
`runtime_type=remote`; all 17 package members and eight Python hashes matched.
Both isolation checks confirmed the internal-only network and no host ports.
Cleanup enabled `validation` and verified zero containers, networks and volumes;
the ephemeral credential/CA-key files were also removed.

The artifact is `dify-remote-debug-40336384519`, ID `12657445840`, 26650 bytes,
SHA-256 `e7b9a5f48d84de90dd474cb3e13a32fcd994f29dded064dcb70fb63dfad54eb3`.
All 11 retained files were audited. Local archive and extracted evidence are in
`.tools/remote-debug-run-40336384519/attempt-2/`. The summary has
`remote_debug_passed=true`, `cloud_passed=false`, and all seven stages `passed`.
The action-runtime deprecation annotation was non-fatal; pinned actions ran on
the runner's Node 24 compatibility mode.

This pass is exclusively for the 125757-byte archive with SHA-256
`ae19e4209a5b9693ca4435df4b0fa8dc3017e4648e6e69743c2452bb0f0c3384`.
It does not transfer to a documentation-replacement archive, even when Python,
manifest, dependencies and icon bytes are identical. Keep the old package and
evidence intact; only update pins after the coordinator supplies a real immutable
Marketplace commit URL for the replacement, then rerun both deployed gates.

## Documentation Replacement Candidate

An unpublished 0.2.0 replacement is staged separately at
`dist/privacy-candidate/flowspeech-0.2.0.difypkg`, 126197 bytes, SHA-256:
`5fc5942eac8185e17f4150da74aceeed2a7c08f935f55b93597f1968a12f05f4`.
The existing verified official Dify packager 0.6.12 was used; its executable hash
was rechecked against the provenance in RELEASE.md before execution.

Only `README.md` and `PRIVACY.md` differ among the 17 archive members. They link
the FlowSpeech privacy policy and API documentation, disclose author-supplied
personal information in scripts/segments, and distinguish the plugin's lack of
an independent local store from Dify's deployment-specific input/output/audio
retention. All eight Python files, the manifest, dependencies and icon are
byte-identical; there are no added or removed members. No website policy was
changed and no new legal or retention guarantee is made.

Source tests: 386 passed. Tests against the extracted replacement: 188 passed.
The two existing SDK warnings remain. Artifact audit and all three workflow
actionlint checks passed. `dist/privacy-candidate/member-diff.json` records every
unchanged Python hash plus manifest/dependency/icon hashes; the source and
artifact XML test reports are beside it.

This candidate has **not** passed deployed CE or remote-debug validation. The
old root `dist/flowspeech-0.2.0.difypkg` and shared pins remain unchanged. The
coordinator must first commit/push the replacement at the existing pending
Marketplace binary path and supply its real immutable commit; only then update
the package URL/hash and root dist copy, recheck tests and rerun both deployed
gates. Do not invent an immutable URL or transfer old runtime evidence to this
new hash. Marketplace readiness remains a separate review decision.
