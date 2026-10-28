"""Offline exact-ID staging checks; no GitHub, credential or Docker access."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest
import yaml

from scripts.deployed_ce import download_qa_candidate as qa
from scripts.deployed_ce import stage_candidate

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = [("deployed-ce.yml", "deployed-ce"), ("remote-debug.yml", "remote-debug")]


@pytest.mark.parametrize("filename,job_name", WORKFLOWS)
def test_same_read_token_only_before_staging_and_docker(filename, job_name):
    workflow = yaml.load((ROOT / ".github/workflows" / filename).read_text(), Loader=yaml.BaseLoader)
    job = workflow["jobs"][job_name]
    assert workflow["permissions"] == {"contents": "read"} and "permissions" not in job
    assert "GH_TOKEN" not in workflow.get("env", {}) and "GH_TOKEN" not in job.get("env", {})
    steps = job["steps"]
    index = next(i for i, item in enumerate(steps) if "scripts.deployed_ce.download_qa_candidate" in item.get("run", ""))
    step = steps[index]
    assert step["timeout-minutes"] == "3" and step["env"] == {"GH_TOKEN": "${{ github.token }}"}
    assert step["run"].strip() == "set -euo pipefail\npython3 -m scripts.deployed_ce.download_qa_candidate"
    checkout = next(i for i, item in enumerate(steps) if "actions/checkout@" in item.get("uses", ""))
    stage = next(i for i, item in enumerate(steps) if "scripts.deployed_ce.stage_candidate" in item.get("run", ""))
    docker = min(i for i, item in enumerate(steps) if "docker " in item.get("run", ""))
    assert checkout < index < stage < docker
    assert steps[checkout]["with"]["persist-credentials"] == "false"
    for i, item in enumerate(steps):
        if i != index:
            assert not any(token in json.dumps(item) for token in ["GH_TOKEN", "GITHUB_TOKEN", "github.token"])
    for name in ["deployed_ce", "remote_debug"]:
        compose = (ROOT / "scripts" / name / "compose.yaml").read_text()
        assert not any(token in compose for token in ["GH_TOKEN", "GITHUB_TOKEN", "github.token"])


def test_production_ids_and_artifact_are_exact():
    assert qa.REPOSITORY == "waeckerlinfederowicz66-sketch/dify-flowspeech-provider"
    assert qa.RELEASE_ID == 426187816 and qa.ASSET_ID == 683534668
    assert qa.TAG == "flowspeech-0.2.1-qa-20261027"
    assert qa.SOURCE_SHA == "22c4d7ce1ceba54ba4b0afb2fbd6fcd97dd7642e"
    assert qa.NAME == "flowspeech-0.2.1.difypkg" and qa.SIZE == 128002
    assert qa.SHA256 == "26933a9636a6d77ff940558c3f1cbaf31d89ebaae0148e020a4ba26289886fe6"
    pins = json.loads((ROOT / "scripts/deployed_ce/pins.json").read_text())
    assert pins["package_sha256"] == qa.SHA256 and pins["package_path"] == "dist/" + qa.NAME


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    payload = b"synthetic-approved-qa-package"
    monkeypatch.setattr(qa, "ROOT", tmp_path)
    monkeypatch.setattr(qa, "SIZE", len(payload))
    monkeypatch.setattr(qa, "SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setenv("GH_TOKEN", "synthetic-step-only-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", qa.REPOSITORY)
    asset = {"id": qa.ASSET_ID, "name": qa.NAME, "size": qa.SIZE,
             "digest": "sha256:" + qa.SHA256, "state": "uploaded"}
    release = {"id": qa.RELEASE_ID, "draft": True, "published_at": None,
               "tag_name": qa.TAG, "target_commitish": qa.SOURCE_SHA, "assets": [copy.deepcopy(asset)]}
    responses = [release, asset, payload]
    calls = []

    def run(args, **kwargs):
        number = len(calls)
        calls.append((args, kwargs))
        prefix = "repos/" + qa.REPOSITORY + "/releases/"
        endpoint = prefix + (str(qa.RELEASE_ID) if number == 0 else "assets/" + str(qa.ASSET_ID))
        accept = "application/octet-stream" if number == 2 else "application/vnd.github+json"
        assert args == ["gh", "api", "--hostname", "github.com", "--method", "GET", endpoint, "--header", "Accept: " + accept]
        assert kwargs["env"]["GH_TOKEN"] == "synthetic-step-only-token"
        assert kwargs["env"]["GODEBUG"] == "http2client=0" and kwargs["env"]["GH_PROMPT_DISABLED"] == "1"
        assert kwargs["capture_output"] is True and kwargs["timeout"] == (60 if number == 2 else 30)
        value = responses[number]
        if isinstance(value, Exception):
            raise value
        if isinstance(value, subprocess.CompletedProcess):
            return value
        return subprocess.CompletedProcess(args, 0, value if isinstance(value, bytes) else json.dumps(value).encode(), b"")

    monkeypatch.setattr(qa.subprocess, "run", run)
    return {"root": tmp_path, "payload": payload, "release": release,
            "asset": asset, "responses": responses, "calls": calls,
            "target": tmp_path / "dist" / qa.NAME}


def test_exact_gets_then_independent_stage_check(fixture, monkeypatch, capsys):
    qa.download()
    assert fixture["target"].read_bytes() == fixture["payload"]
    assert len(fixture["calls"]) == 3
    report = json.loads(capsys.readouterr().out)
    assert report["draft"] is True and report["asset_id"] == qa.ASSET_ID and report["sha256"] == qa.SHA256
    assert "synthetic-step-only-token" not in json.dumps(report)
    root = fixture["root"]
    pins = root / "scripts/deployed_ce/pins.json"
    pins.parent.mkdir(parents=True)
    pins.write_text(json.dumps({"package_path": "dist/" + qa.NAME, "package_sha256": qa.SHA256}))
    monkeypatch.setattr(stage_candidate, "ROOT", root)
    stage_candidate.stage(root / "state")
    assert (root / "state/candidate.difypkg").read_bytes() == fixture["payload"]
    fixture["target"].write_bytes(b"post-download-tamper")
    with pytest.raises(ValueError, match="SHA-256"):
        stage_candidate.stage(root / "tampered-state")


@pytest.mark.parametrize("key,value", [("id", 1), ("draft", False), ("draft", "true"),
    ("published_at", "2026-10-28"), ("tag_name", "wrong-tag"), ("target_commitish", "main"),
    ("assets", []), ("assets", None), ("assets", [{}, {}])])
def test_release_metadata_drift_stops_before_asset_get(fixture, key, value):
    fixture["release"][key] = value
    with pytest.raises(RuntimeError, match="metadata mismatch|inventory mismatch"):
        qa.download()
    assert len(fixture["calls"]) == 1 and not fixture["target"].exists()


@pytest.mark.parametrize("key", ["id", "draft", "published_at", "tag_name", "target_commitish"])
def test_missing_release_fields_fail_closed(fixture, key):
    del fixture["release"][key]
    with pytest.raises(RuntimeError, match="metadata mismatch"):
        qa.download()
    assert len(fixture["calls"]) == 1 and not fixture["target"].exists()


@pytest.mark.parametrize("place", ["release", "asset"])
@pytest.mark.parametrize("key,value", [("id", 1), ("name", "wrong.difypkg"), ("size", 1),
    ("digest", "sha256:" + "0" * 64), ("state", "starter")])
def test_asset_metadata_drift_stops_before_binary_get(fixture, place, key, value):
    asset = fixture["release"]["assets"][0] if place == "release" else fixture["asset"]
    asset[key] = value
    with pytest.raises(RuntimeError, match="asset metadata mismatch"):
        qa.download()
    assert len(fixture["calls"]) == (1 if place == "release" else 2)
    assert not fixture["target"].exists()


@pytest.mark.parametrize("index", [0, 1, 2])
@pytest.mark.parametrize("status", [401, 403, 404])
def test_direct_api_denial_stops_once_without_retry_or_fallback(fixture, index, status, capsys):
    fixture["responses"][index] = subprocess.CompletedProcess([], 1, b"", f"HTTP {status}: synthetic-step-only-token".encode())
    with pytest.raises(RuntimeError, match=f"HTTP {status}.*stop without retry or fallback") as caught:
        qa.download()
    assert len(fixture["calls"]) == index + 1 and not fixture["target"].exists()
    assert "synthetic-step-only-token" not in str(caught.value) + capsys.readouterr().out


@pytest.mark.parametrize("index", [0, 1, 2])
def test_timeout_stops_without_partial_candidate(fixture, index):
    fixture["responses"][index] = subprocess.TimeoutExpired("gh", 30)
    with pytest.raises(RuntimeError, match="timed out"):
        qa.download()
    assert len(fixture["calls"]) == index + 1 and not fixture["target"].exists()


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("value", [b"not-json", [], None])
def test_invalid_metadata_stops(fixture, index, value):
    fixture["responses"][index] = value
    with pytest.raises(RuntimeError, match="Invalid QA metadata"):
        qa.download()
    assert len(fixture["calls"]) == index + 1 and not fixture["target"].exists()


@pytest.mark.parametrize("payload", [b"wrong-size", b"x" * len(b"synthetic-approved-qa-package")])
def test_download_size_and_sha_verified_before_any_candidate_write(fixture, payload):
    fixture["responses"][2] = payload
    with pytest.raises(RuntimeError, match="downloaded bytes mismatch"):
        qa.download()
    assert not fixture["target"].exists()


@pytest.mark.parametrize("symlink", [False, True])
def test_existing_candidate_or_symlink_is_not_overwritten(fixture, symlink):
    target = fixture["target"]
    target.parent.mkdir()
    if symlink:
        target.symlink_to(target.parent / "missing")
    else:
        target.write_bytes(b"preserve")
    with pytest.raises(RuntimeError, match="overwrite"):
        qa.download()
    assert not fixture["calls"]
    if symlink:
        assert target.is_symlink()
    else:
        assert target.read_bytes() == b"preserve"


@pytest.mark.parametrize("defect", ["repository", "token"])
def test_wrong_repo_or_missing_step_token_stops_before_get(fixture, monkeypatch, defect):
    if defect == "repository":
        monkeypatch.setenv("GITHUB_REPOSITORY", "other/repository")
    else:
        monkeypatch.delenv("GH_TOKEN")
    with pytest.raises(RuntimeError, match="repository mismatch|GH_TOKEN is required"):
        qa.download()
    assert not fixture["calls"] and not fixture["target"].exists()
