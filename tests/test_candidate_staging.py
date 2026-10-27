"""The final-artifact gates cannot silently fall back to an older release."""
import hashlib
import json

import pytest

from scripts.deployed_ce import stage_candidate


def configure(tmp_path, monkeypatch):
    source = tmp_path / "dist/flowspeech-0.2.1.difypkg"
    source.parent.mkdir()
    source.write_bytes(b"synthetic-final-candidate")
    pins = tmp_path / "scripts/deployed_ce/pins.json"
    pins.parent.mkdir(parents=True)
    pins.write_text(json.dumps({"package_path": str(source.relative_to(tmp_path)),
                               "package_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}))
    monkeypatch.setattr(stage_candidate, "ROOT", tmp_path)
    return source, tmp_path / "state"


def test_stages_exact_pinned_file_and_refuses_overwrite(tmp_path, monkeypatch):
    source, state = configure(tmp_path, monkeypatch)
    stage_candidate.stage(state)
    assert (state / "candidate.difypkg").read_bytes() == source.read_bytes()
    with pytest.raises(ValueError, match="fresh"):
        stage_candidate.stage(state)


def test_missing_artifact_does_not_create_state(tmp_path, monkeypatch):
    source, state = configure(tmp_path, monkeypatch)
    source.unlink()
    with pytest.raises(ValueError, match="Coordinator must stage"):
        stage_candidate.stage(state)
    assert not state.exists()


def test_wrong_bytes_cannot_be_staged(tmp_path, monkeypatch):
    source, state = configure(tmp_path, monkeypatch)
    source.write_bytes(b"older-release")
    with pytest.raises(ValueError, match="SHA-256"):
        stage_candidate.stage(state)
    assert not state.exists()


def test_explicit_source_still_requires_final_hash(tmp_path, monkeypatch):
    source, state = configure(tmp_path, monkeypatch)
    alternate = tmp_path / "alternate.difypkg"
    alternate.write_bytes(source.read_bytes())
    stage_candidate.stage(state, alternate)
    assert (state / "candidate.difypkg").read_bytes() == alternate.read_bytes()
