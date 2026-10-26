"""Inspect built distributions without executing package contents."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

FORBIDDEN = {".env", ".git", ".venv", "__pycache__", ".pytest_cache", ".tools",
             ".artifact-test", ".test-tmp", "vendor"}
SECRET = re.compile(rb"(?:pypi-[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|"
                    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
                    rb"(?:sk_live_|fs_live_)[A-Za-z0-9_-]{24,})")


def inspect(path):
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            entries = []
            for member in archive.getmembers():
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError("Non-file archive member")
                entries.append((member.name, archive.extractfile(member).read()))
    else:
        with zipfile.ZipFile(path) as archive:
            entries = []
            for member in archive.infolist():
                if member.is_dir():
                    continue
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Symlink archive member")
                entries.append((member.filename, archive.read(member)))
    for name, content in entries:
        parts = PurePosixPath(name).parts
        assert not name.startswith("/") and ".." not in parts, name
        assert not (set(parts) & FORBIDDEN), name
        assert not any(p.startswith(".env") for p in parts), name
        assert not name.endswith((".pyc", ".whl", ".difypkg", ".exe")), name
        assert not SECRET.search(content), "Potential secret in " + name
        assert b"/Users/" not in content and b"/private/var/folders/" not in content, "Private local path in " + name
        if path.suffix in {".whl", ".difypkg"}:
            assert "tests" not in parts and "test-only" not in content.decode("utf-8", errors="ignore"), name
    assert sum(len(content) for _, content in entries) <= 100 * 1024 * 1024
    if path.suffix == ".whl":
        metadata = next(content for name, content in entries if name.endswith(".dist-info/METADATA"))
        assert b"Version: 0.2.0\n" in metadata
        assert b"Requires-Dist: httpx" in metadata
    if path.suffix == ".difypkg":
        assert {"main.py", "runtime_config.py", "flowspeech_v1.py"} <= set(dict(entries))
        manifest = dict(entries)["manifest.yaml"]
        assert manifest.startswith(b"version: 0.2.0")
    return {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size, "members": [name for name, _ in entries],
            "secrets_or_unintended_members": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--extract-dify", type=Path)
    args = parser.parse_args()
    results = [inspect(path) for path in args.paths]
    if args.extract_dify:
        assert len(args.paths) == 1 and args.paths[0].suffix == ".difypkg"
        assert not args.extract_dify.exists(), "Use a fresh artifact test directory"
        with zipfile.ZipFile(args.paths[0]) as archive:
            archive.extractall(args.extract_dify)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

