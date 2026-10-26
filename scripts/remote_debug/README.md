# Supplemental Remote-Debug Gate

This independent, bounded CI job tests Dify's official TCP remote-debug protocol.
It does not replace or modify the passed full CE gate (run `40326427753`, head
`4ff46caacca3abfbe7615f6099009baf6c42ce4e`). **The remote-debug deployment has not
yet run: local unit tests and workflow lint are not a remote-protocol pass.**

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
egress-policy validation remain untested. Keep the Marketplace draft and relevant
guideline checkbox pending actual remote-protocol success and evidence review.

## Exact Candidate and Isolation

Reuse `scripts/deployed_ce/pins.json`: CE 1.18.0, Go daemon 0.6.10-local, Python
3.12.14, and all five Docker images by digest. The immutable package is
`flowspeech-0.2.0.difypkg`, 125757 bytes, SHA-256:

`ae19e4209a5b9693ca4435df4b0fa8dc3017e4648e6e69743c2452bb0f0c3384`

All 17 members, including all eight Python files, are compared byte-for-byte
before execution; per-Python-file hashes are retained. No plugin code, manifest,
requirements, package or original entrypoint is changed or repackaged. The
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

Review the local commit, then push `codex/public-api-v1`. The new workflow's
path filter starts the supplemental gate without retriggering the unchanged
full CE workflow. A manual alternative after push is:

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
development harness test files excluded. Do not rebuild the reviewed package.

## Local Candidate Validation

The candidate preparation checks passed on Python 3.12.14: 84 supplemental-gate
tests, 384 total source tests, and 188 tests against the unchanged extracted
release package. Source/artifact suites retain the two existing SDK warnings
(gevent SSL import order and deprecated Pydantic class configuration).
Actionlint 1.7.7 passed all three workflows. The artifact audit and a fresh
extraction verified all 17 members and eight Python-file hashes.

Ignored local review evidence is under `.tools/remote-debug-candidate/`:
`source-tests.xml`, `artifact-tests.xml`, and `package-identity.json`.
There is no remote deployment evidence yet, because this machine has no Docker
engine. No public push, workflow dispatch or Marketplace state change was made
while preparing this candidate.
