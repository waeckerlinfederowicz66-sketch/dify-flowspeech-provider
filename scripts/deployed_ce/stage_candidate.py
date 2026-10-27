"""Stage only the locally supplied, final-hash candidate; never fetch a release."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]


def stage(state: Path, source: Path | None = None) -> None:
    pins = json.loads((ROOT / "scripts/deployed_ce/pins.json").read_text())
    source = source or ROOT / pins["package_path"]
    if not source.is_file():
        raise ValueError("Coordinator must stage the exact final artifact locally before this gate")
    if hashlib.sha256(source.read_bytes()).hexdigest() != pins["package_sha256"]:
        raise ValueError("Candidate SHA-256 does not match the final release pin")
    state.mkdir(parents=True, exist_ok=True)
    target = state / "candidate.difypkg"
    if target.exists():
        raise ValueError("Use a fresh candidate state directory")
    shutil.copyfile(source, target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    stage(args.state, args.source)
