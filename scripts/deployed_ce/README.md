# Deployed CE Release Gate

The current candidate in `pins.json` is the 126197-byte documentation replacement
at immutable Marketplace commit `1024cfe3385e390626e0e4253b23d4c6b9469651`, SHA-256
`5fc5942eac8185e17f4150da74aceeed2a7c08f935f55b93597f1968a12f05f4`.
Its full CE and remote-debug deployed checks are pending; pushing the shared pins
triggers both gates. No old result is transferred to the replacement.

The complete defined **isolated headless CE gate passed for the previous package** in
[run 40326427753](https://github.com/waeckerlinfederowicz66-sketch/dify-flowspeech-provider/actions/runs/40326427753)
at head 4ff46caacca3abfbe7615f6099009baf6c42ce4e. Slow completion took 200.301s;
after a 3.103s quota-only restart probe, host 180/tool 175 returned recovery at
170.257s with one submission and no audio. All other cases, exact persisted WAV
hashes, credential-free downloads and both isolation checks passed. The retained
summary has ce_passed=true and cloud_passed=false. Its package SHA-256 is
`ae19e4209a5b9693ca4435df4b0fa8dc3017e4648e6e69743c2452bb0f0c3384`;
see VALIDATION.md for the historical audit.
Keep Marketplace PR [3513](https://github.com/langgenius/dify-plugins/pull/3513)
draft until the coordinator reviews actual CI evidence and the Cloud limitation.

## Coordinator Handoff

Push the reviewed changes to `codex/public-api-v1` in
`waeckerlinfederowicz66-sketch/dify-flowspeech-provider`. Changes to this directory
or `.github/workflows/deployed-ce.yml` trigger the next run automatically.
The worker does not push or dispatch workflows.

    gh run list --repo waeckerlinfederowicz66-sketch/dify-flowspeech-provider --workflow deployed-ce.yml --branch codex/public-api-v1 --limit 3
    gh run watch RUN_ID --repo waeckerlinfederowicz66-sketch/dify-flowspeech-provider --exit-status
    gh run download RUN_ID --repo waeckerlinfederowicz66-sketch/dify-flowspeech-provider --name dify-ce-validation-RUN_ID

Once the workflow is registered on the repository's default branch, manual
reruns can also use:

    gh workflow run deployed-ce.yml --repo waeckerlinfederowicz66-sketch/dify-flowspeech-provider --ref codex/public-api-v1

Before committing, verify `git config --local user.email` is
`waeckerlinfederowicz66@gmail.com`. Do not change global identity or rewrite
published history. No GitHub, Dify Cloud, or FlowSpeech secrets are needed by CI.

## Bounded Deployment

One standard `ubuntu-22.04` GitHub-hosted job, at most 40 minutes. Images, actions,
source references, and the reviewed candidate are pinned in `pins.json` and the
workflow. The artifact is downloaded from the immutable Marketplace PR commit,
verified against SHA-256, audited, and installed through CE's console upload/install
APIs. It is not rebuilt, repackaged, imported directly, or substituted with a shim.

The real services are Dify CE API, Celery worker, Go plugin daemon, PostgreSQL,
and Redis. A separate HTTPS mock and console-API driver run on the same private
network. There is no browser, model node, Cloud deployment, external reverse
proxy, or production generation. No container port or Docker socket is exposed.

Dependencies are downloaded as binary wheels before starting CE. The daemon
installs them offline with `--no-index`. Every deployed container uses a Docker
`internal` network (or no network), verified before installation. Docker's none
entry is accepted only in mode none with no IP addresses or routes; it is not an
allowlisted routable network. Host ports and privileged/socket access remain
forbidden. Failure evidence contains only service, mode and attached network
names, never raw inspect environment variables. DNS aliases
`flowspeech.io` and `static.flowspeech.io` resolve only to the mock container.
No missing mock can fall back to the production API.

The candidate disables environment proxy/CA settings with `trust_env=False`.
Therefore the test adds its disposable public CA to the installed runtime's
certifi trust bundle after installation. It verifies every installed plugin Python
file against the original archive before doing so. Plugin source, SDK dispatch,
HTTP transport, polling clocks and WAV parsing are not monkey-patched.
Signature verification is disabled only in this disposable CE instance to permit
the unsigned review candidate; this does not prove Marketplace signature acceptance.

## Required Evidence

- Actual daemon installation with the expected unique identifier and local runtime.
- Rejected invalid provider credentials; successful real quota validation and
  encrypted credential storage through CE. Validation must not create audio.
- A start/tool/end workflow downloads the WAV from CE's persisted file service,
  compares its exact bytes, and retains job/request recovery metadata.
- A real 200-second job completes with host 300/tool 295. No simulated clock.
- Malformed WAV and API/unsafe-audio redirects produce recovery errors, no audio,
  no redirect follow, and exactly one job submission.
- A safe HTTPS audio redirect between the two isolated hosts produces one persisted
  WAV through exactly two credential-free download hops and one submission.
- A short requested deadline returns recovery metadata without resubmission.
- Restart the actual daemon with host 180 and wait at most 90 seconds for actual
  invalid-credential dispatch to reach only quota, with no saved credential or job.
  Retry only the known runtime-not-found startup response; other errors fail.
  Then a single 200-second pending job returns
  recovery before 180 seconds, exercising the tool's 175-second cap.
- Storage downloads never contain Authorization or cookies; default polls are
  separated by at least five seconds, allowing small measurement tolerance.

Retained evidence includes `install.json`, `run.json`, `short-host.json`,
`runtime-identity.json`, `isolation.json`, persisted WAV hashes, failed-case mock
audits when available, package audit, pinned image/package
identities, dependency-wheel hashes, and bounded redacted service logs.
`summary.json` reports CE success only when isolation and all three stages pass and always
reports Cloud as unvalidated. A failed diagnostics redaction check prevents
artifact upload. Settings, credentials, CA private keys, cookies, wheels, database
volumes, and raw workflow responses are never uploaded. Cleanup removes only this
job's Compose project and volumes; artifacts expire after seven days.

## Scope and Remaining Gates

1. This workstation has no Docker/Podman/Colima. The CE pass is from the real
   GitHub-hosted deployment of the previous package, including the post-restart 180-second stage, not
   the source/SDK simulations. An integration failure in a future run must still
   fail the gate; do not substitute an SDK-only check.
2. The historical passing run covers its pinned headless CE configuration only. It does not
   validate the web UI, a separately deployed reverse proxy, actual production
   storage overrides, other CE versions, or Dify Cloud's managed policies.
3. Cloud needs a reviewer-authorized workspace with plugin-install/workflow
   permissions and platform-controlled mock routing plus certificate trust for
   the plugin's fixed HTTPS hosts. Those facilities have not been supplied.
   Ordinary Cloud workspace access alone cannot safely redirect this unchanged
   package to a mock. Do not invoke production endpoints or change the package to
   manufacture a Cloud pass. Document this unvalidated scope for reviewer acceptance;
   the Marketplace template permits documented limitations rather than requiring
   an unconditional Cloud pass. PR 3513 readiness remains the coordinator's decision.

## References

- [CE deployment guidance](https://docs.dify.ai/en/self-host/deploy/quick-start/docker-compose)
- [Pinned CE console plugin routes](https://github.com/langgenius/dify/blob/50abea97062110044f15d0e03ccecadd9ccc87ca/api/controllers/console/workspace/plugin.py)
- [Pinned CE workflow routes](https://github.com/langgenius/dify/blob/50abea97062110044f15d0e03ccecadd9ccc87ca/api/controllers/console/app/workflow.py)
- [Pinned daemon process environment](https://github.com/langgenius/dify-plugin-daemon/blob/1310a18b2f6bc6f18768a0a6265484830891433c/internal/core/local_runtime/subprocess.go)
- [Marketplace submission requirements](https://github.com/langgenius/dify-plugins/blob/main/docs/plugin-submission-requirements.md)
