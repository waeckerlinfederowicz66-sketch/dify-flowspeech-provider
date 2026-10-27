"""Offline checks of the exact-asset pre-stage step, without GitHub or Docker."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts.deployed_ce import stage_candidate

ROOT = Path(__file__).resolve().parents[1]
SHA = "26933a9636a6d77ff940558c3f1cbaf31d89ebaae0148e020a4ba26289886fe6"
TAG = "flowspeech-0.2.1-qa-20261027"
NAME = "flowspeech-0.2.1.difypkg"
REPO = "waeckerlinfederowicz66-sketch/dify-flowspeech-provider"
WORKFLOWS = [("deployed-ce.yml", "deployed-ce"), ("remote-debug.yml", "remote-debug")]


def workflow(filename, job):
    document = yaml.load((ROOT / ".github/workflows" / filename).read_text(), Loader=yaml.BaseLoader)
    return document, document["jobs"][job]


def download_step(job):
    return next(step for step in job["steps"] if "gh release download" in step.get("run", ""))


@pytest.mark.parametrize("filename,job_name", WORKFLOWS)
def test_exact_asset_is_bounded_read_only_and_precedes_all_deployment(filename, job_name):
    document, job = workflow(filename, job_name)
    assert document["permissions"] == {"contents": "read"}
    assert "permissions" not in job
    assert "GH_TOKEN" not in document.get("env", {}) and "GH_TOKEN" not in job.get("env", {})
    steps = job["steps"]
    download = download_step(job)
    assert download["timeout-minutes"] == "3"
    assert download["env"] == {"GH_TOKEN": "${{ github.token }}"}
    index = steps.index(download)
    checkout = next(i for i, step in enumerate(steps) if "actions/checkout@" in step.get("uses", ""))
    stage = next(i for i, step in enumerate(steps) if "scripts.deployed_ce.stage_candidate" in step.get("run", ""))
    containers = [i for i, step in enumerate(steps) if "docker " in step.get("run", "")]
    assert checkout < index < stage < min(containers)
    assert steps[checkout]["with"]["persist-credentials"] == "false"
    command = download["run"]
    assert f"gh release download {TAG}" in command
    assert '--repo "$GITHUB_REPOSITORY"' in command
    assert f"--pattern {NAME}" in command and '--dir "$GITHUB_WORKSPACE/dist"' in command
    assert SHA in command and "sha256sum --check --strict" in command
    assert "set -euo pipefail" in command
    assert not any(value in command for value in ["$GITHUB_ENV", "--clobber", "docker ", "gh release create", "gh release upload"])
    for i, step in enumerate(steps):
        if i != index:
            assert not any(token in json.dumps(step) for token in ["GH_TOKEN", "GITHUB_TOKEN", "github.token"])
    for compose in ["scripts/deployed_ce/compose.yaml", "scripts/remote_debug/compose.yaml"]:
        assert not any(token in (ROOT / compose).read_text() for token in ["GH_TOKEN", "GITHUB_TOKEN", "github.token"])


def executable(path, source):
    path.write_text("#!" + sys.executable + "\n" + source)
    path.chmod(0o700)


@pytest.mark.parametrize("filename,job_name", WORKFLOWS)
@pytest.mark.parametrize("defect", [None, "wrong-bytes", "missing-asset", "existing-file"])
def test_actual_shell_downloads_only_exact_fixture_and_fails_closed(tmp_path, monkeypatch, filename, job_name, defect):
    _, job = workflow(filename, job_name)
    step = download_step(job)
    workspace = tmp_path / "checkout with spaces"
    workspace.mkdir()
    binary = tmp_path / "bin"
    binary.mkdir()
    payload = b"synthetic-approved-final-package"
    expected_sha = hashlib.sha256(payload).hexdigest()
    fixture = tmp_path / "fixture.difypkg"
    fixture.write_bytes(b"wrong-bytes" if defect == "wrong-bytes" else payload)
    executable(binary / "gh", """import json, os, pathlib, sys
args = sys.argv[1:]
assert args == ['release', 'download', 'flowspeech-0.2.1-qa-20261027', '--repo',
                'waeckerlinfederowicz66-sketch/dify-flowspeech-provider', '--pattern',
                'flowspeech-0.2.1.difypkg', '--dir', os.environ['GITHUB_WORKSPACE'] + '/dist']
assert os.environ['GH_TOKEN'] == 'synthetic-step-only-token'
pathlib.Path(os.environ['QA_RECORD']).write_text(json.dumps({'args': args, 'token_present': True}))
if os.environ['QA_DEFECT'] == 'missing-asset':
    sys.exit(1)
target = pathlib.Path(args[-1]) / 'flowspeech-0.2.1.difypkg'
if target.exists():
    sys.exit(2)
target.write_bytes(pathlib.Path(os.environ['QA_FIXTURE']).read_bytes())
""")
    executable(binary / "sha256sum", """import hashlib, pathlib, sys
assert sys.argv[1:] == ['--check', '--strict']
lines = sys.stdin.read().splitlines()
assert len(lines) == 1
expected, filename = lines[0].split('  ', 1)
assert pathlib.Path(filename).name == 'flowspeech-0.2.1.difypkg'
sys.exit(0 if hashlib.sha256(pathlib.Path(filename).read_bytes()).hexdigest() == expected else 1)
""")
    target = workspace / "dist" / NAME
    if defect == "existing-file":
        target.parent.mkdir()
        target.write_bytes(b"preserve-existing-file")
    record = tmp_path / "gh-record.json"
    env = {"PATH": str(binary) + os.pathsep + os.defpath, "HOME": str(tmp_path),
           "PYTHONDONTWRITEBYTECODE": "1", "GH_TOKEN": "synthetic-step-only-token",
           "GITHUB_REPOSITORY": REPO, "GITHUB_WORKSPACE": str(workspace),
           "QA_RECORD": str(record), "QA_FIXTURE": str(fixture), "QA_DEFECT": defect or ""}
    # Only the fixture checksum changes; the static test above independently pins the production SHA.
    result = subprocess.run(["bash", "-c", step["run"].replace(SHA, expected_sha)],
                            env=env, cwd=workspace, capture_output=True, text=True, timeout=10)
    assert (result.returncode == 0) is (defect is None)
    assert "synthetic-step-only-token" not in result.stdout + result.stderr
    assert json.loads(record.read_text())["token_present"] is True
    if defect == "existing-file":
        assert target.read_bytes() == b"preserve-existing-file"
    elif defect == "missing-asset":
        assert not target.exists()
    if defect is not None:
        return
    assert target.read_bytes() == payload
    pins = workspace / "scripts/deployed_ce/pins.json"
    pins.parent.mkdir(parents=True)
    pins.write_text(json.dumps({"package_path": "dist/" + NAME, "package_sha256": expected_sha}))
    monkeypatch.setattr(stage_candidate, "ROOT", workspace)
    state = tmp_path / "independently-verified-state"
    stage_candidate.stage(state)
    assert (state / "candidate.difypkg").read_bytes() == payload
    target.write_bytes(b"tampered-after-workflow-check")
    with pytest.raises(ValueError, match="SHA-256"):
        stage_candidate.stage(tmp_path / "tampered-state")
