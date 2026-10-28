"""Offline independent-build regressions; no network, ELF execution or Docker."""
import copy
import io
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile

import pytest
import yaml

from scripts.deployed_ce import build_qa_candidate as qa
from scripts.deployed_ce import stage_candidate

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = [("deployed-ce.yml", "deployed-ce"), ("remote-debug.yml", "remote-debug")]


@pytest.mark.parametrize("filename,job_name", WORKFLOWS)
def test_independent_build_before_unchanged_stage_and_docker_without_tokens(filename, job_name):
    workflow = yaml.load((ROOT / ".github/workflows" / filename).read_text(), Loader=yaml.BaseLoader)
    job = workflow["jobs"][job_name]
    assert workflow["permissions"] == {"contents": "read"} and "permissions" not in job
    assert not any(token in json.dumps(workflow) for token in ("GH_TOKEN", "GITHUB_TOKEN", "github.token", "secrets."))
    steps = job["steps"]
    index = next(i for i, item in enumerate(steps) if "scripts.deployed_ce.build_qa_candidate" in item.get("run", ""))
    step = steps[index]
    assert step["timeout-minutes"] == "5" and "env" not in step
    assert step["run"].strip() == 'set -euo pipefail\npython3 -m scripts.deployed_ce.build_qa_candidate "$GATE_STATE-build"'
    checkout = next(i for i, item in enumerate(steps) if "actions/checkout@" in item.get("uses", ""))
    stage = next(i for i, item in enumerate(steps) if "scripts.deployed_ce.stage_candidate" in item.get("run", ""))
    docker = min(i for i, item in enumerate(steps) if "docker " in item.get("run", ""))
    assert checkout < index < stage < docker
    assert '--source "$GATE_STATE-build/candidate.difypkg"' in steps[stage]["run"]
    prepare = "python3 scripts/deployed_ce/prepare.py" if job_name == "deployed-ce" else "python3 -m scripts.remote_debug.prepare"
    copy_proof = 'cp -- "$GATE_STATE-build/build-proof.json" "$GATE_STATE/evidence/build-proof.json"'
    assert copy_proof in steps[stage]["run"]
    assert steps[stage]["run"].index(prepare) < steps[stage]["run"].index(copy_proof)
    assert steps[-1]["with"]["path"] == "${{ runner.temp }}/" + ("flowspeech-ce-gate" if job_name == "deployed-ce" else "flowspeech-remote-gate") + "/evidence/"
    assert not any('"$GATE_STATE-build"' in item.get("run", "") for item in steps[stage:])
    assert steps[checkout]["with"]["persist-credentials"] == "false"
    assert "download_qa_candidate" not in json.dumps(workflow)
    for name in ("deployed_ce", "remote_debug"):
        compose = (ROOT / "scripts" / name / "compose.yaml").read_text()
        assert not any(token in compose for token in ("GH_TOKEN", "GITHUB_TOKEN", "github.token"))


def test_official_public_cli_and_frozen_pins():
    assert qa.CLI_VERSION == "v0.6.12"
    assert qa.CLI_URL == "https://github.com/langgenius/dify-plugin-daemon/releases/download/0.6.12/dify-plugin-linux-amd64"
    assert qa.CLI_SHA256 == "f5190893643492c3f17f12c9752615a5652e47bbf30e84298634e176611aa108"
    assert qa.PACKAGE_SHA256 == "26933a9636a6d77ff940558c3f1cbaf31d89ebaae0148e020a4ba26289886fe6"
    assert qa.PACKAGE_SIZE == 128002 and qa.MEMBER_COUNT == 17
    pins = json.loads((ROOT / "scripts/deployed_ce/build-inputs.json").read_text())
    qa.verify_inputs(ROOT, pins)
    frozen = ROOT / "dist/flowspeech-0.2.1.difypkg"
    if frozen.exists():
        qa.verify_package(frozen, pins)
    stage = json.loads((ROOT / "scripts/deployed_ce/pins.json").read_text())
    assert stage["package_sha256"] == qa.PACKAGE_SHA256


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    root.mkdir()
    work = tmp_path / "fresh-build"
    inputs = {f"member-{index:02d}.txt": f"synthetic-{index}".encode() for index in range(17)}
    records = [{"path": name, "bytes": len(data), "sha256": qa.digest(data)} for name, data in sorted(inputs.items())]
    source_filter = b"scripts/\ntests/\n"
    pins = {"members": records, "source_filter": {"path": ".difyignore", "bytes": len(source_filter), "sha256": qa.digest(source_filter)}}
    pin_file = root / "scripts/deployed_ce/build-inputs.json"
    pin_file.parent.mkdir(parents=True)
    pin_file.write_text(json.dumps(pins))
    package_buffer = io.BytesIO()
    with zipfile.ZipFile(package_buffer, "w") as bundle:
        for name, data in sorted(inputs.items()):
            bundle.writestr(name, data)
    package = package_buffer.getvalue()
    def encoded_string(value):
        assert len(value) < 128
        return bytes([len(value)]) + value

    header = bytes.fromhex("ff20476f206275696c64696e663a") + b"\x08\x02" + b"\0" * 16
    module = b"\0" * 16 + b"path\tsynthetic/cli\nbuild\tGOOS=linux\nbuild\tGOARCH=amd64\n" + b"\0" * 16
    cli = (b"\x7fELF\x02\x01" + b"\0" * 12 + b"\x3e\x00" + header
           + encoded_string(b"go1.synthetic") + encoded_string(module))
    monkeypatch.setattr(qa, "ROOT", root)
    monkeypatch.setattr(qa, "CLI_SHA256", qa.digest(cli))
    monkeypatch.setattr(qa, "PACKAGE_SIZE", len(package))
    monkeypatch.setattr(qa, "PACKAGE_SHA256", qa.digest(package))
    monkeypatch.setattr(qa.platform, "system", lambda: "Linux")
    monkeypatch.setattr(qa.platform, "machine", lambda: "x86_64")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "DIFY_API_KEY", "HTTPS_PROXY"):
        monkeypatch.setenv(name, "synthetic-must-not-leak")
    calls = []
    state = {"cli": cli, "version": qa.CLI_VERSION, "package": package, "inputs": inputs,
             "filter": source_filter, "archive_extra": None, "failure": None}

    def run(args, **kwargs):
        calls.append((args, kwargs))
        env = kwargs["env"]
        assert set(env) == {"PATH", "HOME", "TMPDIR", "LC_ALL", "TZ", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL", "GIT_TERMINAL_PROMPT"}
        assert "synthetic-must-not-leak" not in json.dumps(env)
        assert kwargs["capture_output"] is True and kwargs["timeout"] <= 130
        assert not any(word in " ".join(args) for word in ("gh api", "releases/assets", "426187816", "683534668"))
        if state["failure"]:
            raise state["failure"]
        output = ""
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            output = "a" * 40
        elif args[:2] == ["git", "archive"]:
            with tarfile.open(work / "source.tar", "w") as bundle:
                for name, data in {**state["inputs"], ".difyignore": state["filter"]}.items():
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    bundle.addfile(member, io.BytesIO(data))
                if state["archive_extra"]:
                    bundle.addfile(state["archive_extra"])
        elif args[0] == "curl":
            assert args[-1] == qa.CLI_URL
            assert "--disable" in args and "--proto" in args and "=https" in args
            assert not any(option in args for option in ("--header", "--user", "--netrc", "--retry"))
            (work / "dify-plugin-linux-amd64").write_bytes(state["cli"])
        elif args == [str(work / "dify-plugin-linux-amd64"), "version"]:
            output = state["version"]
        else:
            assert args == [str(work / "dify-plugin-linux-amd64"), "plugin", "package", ".", "-o", str(work / "candidate.difypkg")]
            assert kwargs["cwd"] == work / "source"
            (work / "candidate.difypkg").write_bytes(state["package"])
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(qa.subprocess, "run", run)
    return {"root": root, "work": work, "state": state, "calls": calls, "pins": pins, "package": package}


def test_build_then_unchanged_independent_stage_check(fixture, monkeypatch, capsys):
    report = qa.build(fixture["work"])
    assert len(fixture["calls"]) == 5
    assert report["acquisition_credentials"] is False and len(report["members"]) == 17
    assert "synthetic-must-not-leak" not in capsys.readouterr().out
    root = fixture["root"]
    (root / "scripts/deployed_ce/pins.json").write_text(json.dumps({"package_sha256": qa.PACKAGE_SHA256}))
    monkeypatch.setattr(stage_candidate, "ROOT", root)
    candidate = fixture["work"] / "candidate.difypkg"
    stage_candidate.stage(root.parent / "staged", candidate)
    assert (root.parent / "staged/candidate.difypkg").read_bytes() == fixture["package"]
    candidate.write_bytes(b"tampered-after-build")
    with pytest.raises(ValueError, match="SHA-256"):
        stage_candidate.stage(root.parent / "bad-stage", candidate)


@pytest.mark.parametrize("system,machine", [("Darwin", "arm64"), ("Darwin", "x86_64"), ("Linux", "aarch64")])
def test_no_elf_execution_or_download_on_wrong_platform(fixture, monkeypatch, system, machine):
    monkeypatch.setattr(qa.platform, "system", lambda: system)
    monkeypatch.setattr(qa.platform, "machine", lambda: machine)
    with pytest.raises(RuntimeError, match="Linux AMD64 only"):
        qa.build(fixture["work"])
    assert fixture["calls"] == [] and not fixture["work"].exists()


@pytest.mark.parametrize("defect", ["existing", "symlink", "checkout"])
def test_no_existing_output_or_checkout_mutation(fixture, defect):
    work = fixture["work"]
    if defect == "existing":
        work.mkdir()
    elif defect == "symlink":
        work.symlink_to(work.parent / "missing")
    else:
        work = fixture["root"] / "new"
    with pytest.raises(RuntimeError, match="workspace"):
        qa.build(work)
    assert not fixture["calls"]


@pytest.mark.parametrize("defect", ["missing", "content", "filter", "path", "symlink"])
def test_bad_export_stops_before_public_cli_download(fixture, defect):
    state = fixture["state"]
    if defect == "missing":
        del state["inputs"]["member-00.txt"]
    elif defect == "content":
        state["inputs"]["member-00.txt"] = b"drift"
    elif defect == "filter":
        state["filter"] = b"drift"
    else:
        item = tarfile.TarInfo("../unsafe" if defect == "path" else "link")
        if defect == "symlink":
            item.type = tarfile.SYMTYPE
            item.linkname = "member-00.txt"
        state["archive_extra"] = item
    with pytest.raises(RuntimeError, match="input|export|Export"):
        qa.build(fixture["work"])
    assert len(fixture["calls"]) == 2


@pytest.mark.parametrize("defect", ["sha", "elf", "version", "provenance"])
def test_bad_cli_never_packages(fixture, monkeypatch, defect):
    state = fixture["state"]
    if defect == "sha":
        state["cli"] += b"drift"
    elif defect == "elf":
        state["cli"] = b"not-elf"
        monkeypatch.setattr(qa, "CLI_SHA256", qa.digest(state["cli"]))
    elif defect == "provenance":
        state["cli"] = state["cli"].replace(b"GOOS=linux", b"GOOS=other")
        monkeypatch.setattr(qa, "CLI_SHA256", qa.digest(state["cli"]))
    else:
        state["version"] = "v0.6.11"
    with pytest.raises(RuntimeError, match="CLI|ELF"):
        qa.build(fixture["work"])
    assert len(fixture["calls"]) == (4 if defect == "version" else 3)
    assert not (fixture["work"] / "candidate.difypkg").exists()


@pytest.mark.parametrize("data", [b"", bytes.fromhex("ff20476f206275696c64696e663a") + b"\0" * 40])
def test_missing_go_provenance_stops_without_elf_execution(data):
    with pytest.raises(RuntimeError, match="Go build information"):
        qa.cli_provenance(data)


@pytest.mark.parametrize("defect", ["size", "hash"])
def test_package_hash_size_mismatch_stops_before_proof(fixture, defect):
    payload = b"wrong-size" if defect == "size" else b"x" * len(fixture["package"])
    fixture["state"]["package"] = payload
    with pytest.raises(RuntimeError, match="frozen size/SHA-256"):
        qa.build(fixture["work"])
    assert not (fixture["work"] / "build-proof.json").exists()


@pytest.mark.parametrize("defect", ["count", "member-hash", "member-size"])
def test_zip_member_checks_are_independent_of_whole_package_hash(fixture, defect):
    candidate = fixture["root"] / "synthetic.zip"
    candidate.write_bytes(fixture["package"])
    pins = copy.deepcopy(fixture["pins"])
    if defect == "count":
        pins["members"].pop()
    elif defect == "member-hash":
        pins["members"][0]["sha256"] = "0" * 64
    else:
        pins["members"][0]["bytes"] += 1
    with pytest.raises(RuntimeError, match="inventory|member hash/size"):
        qa.verify_package(candidate, pins)


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired("synthetic", 1), OSError("synthetic-must-not-leak")])
def test_command_failure_no_retry_fallback_or_credential_leak(fixture, error):
    fixture["state"]["failure"] = error
    with pytest.raises(RuntimeError, match="unavailable or timed out") as caught:
        qa.build(fixture["work"])
    assert len(fixture["calls"]) == 1
    assert "synthetic-must-not-leak" not in str(caught.value)


def test_wrong_source_commit_stops_before_export(fixture, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    with pytest.raises(RuntimeError, match="workflow source"):
        qa.build(fixture["work"])
    assert len(fixture["calls"]) == 1


def test_nonzero_command_stops_with_redacted_error(tmp_path, monkeypatch):
    monkeypatch.setattr(qa.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess([], 1, "secret", "secret"))
    with pytest.raises(RuntimeError, match="stop without fallback") as caught:
        qa.run(["synthetic"], tmp_path, {}, 1)
    assert "secret" not in str(caught.value)


def test_only_named_build_proof_is_allowed_and_existing_secret_checks_still_apply(tmp_path):
    from scripts.remote_debug import collect

    expected = {name + ".json" for name in collect.STAGES} | {"pins.json", "package-audit.json", "summary.json", "service-logs.txt", "build-proof.json"}
    assert collect.ALLOWED == expected
    proof = tmp_path / "build-proof.json"
    proof.write_text(json.dumps({"source_commit": "a" * 40, "cli_build_provenance": {"go_version": "go1.synthetic"}}))
    collect.check_evidence(tmp_path, [])
    proof.write_text(json.dumps({"accidental": "synthetic-private-credential"}))
    with pytest.raises(AssertionError, match="credential"):
        collect.check_evidence(tmp_path, ["synthetic-private-credential"])
