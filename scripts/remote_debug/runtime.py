"""Offline environment setup and original entrypoint execution, never an SDK shim."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import zipfile


def identity(package: Path, root: Path, expected_sha: str) -> dict:
    assert hashlib.sha256(package.read_bytes()).hexdigest() == expected_sha, "Package hash changed"
    with zipfile.ZipFile(package) as archive:
        expected = {i.filename: archive.read(i) for i in archive.infolist() if not i.is_dir()}
    actual = {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}
    assert set(actual) == set(expected), "Extracted package member set changed"
    assert not any(p.is_symlink() for p in root.rglob("*")), "Unexpected symlink"
    for name, content in expected.items():
        assert actual[name].read_bytes() == content, "Package member changed: " + name
    python = {name: hashlib.sha256(content).hexdigest() for name, content in expected.items() if name.endswith(".py")}
    assert len(python) == 8, "Expected exactly eight reviewed Python files"
    return {"status": "passed", "package_sha256": expected_sha, "all_members_matched": len(expected),
            "python_files_matched": 8, "python_sha256": python, "plugin_code_changed": False}


def trust_ca(venv: Path, ca: Path) -> str:
    bundles = list(venv.glob("lib/python*/site-packages/certifi/cacert.pem"))
    assert len(bundles) == 1, "Expected one disposable certifi bundle"
    content = ca.read_bytes()
    assert content.startswith(b"-----BEGIN CERTIFICATE-----")
    original = bundles[0].read_bytes()
    if content not in original:
        bundles[0].write_bytes(original + b"\n" + content)
    return hashlib.sha256(content).hexdigest()


def launch_environment(key: str) -> dict:
    assert str(uuid.UUID(key)) == key, "Invalid debugging key format"
    return {"PATH": "/runtime/venv/bin:/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp",
            "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1",
            "INSTALL_METHOD": "remote", "REMOTE_INSTALL_URL": "plugin_daemon:5003",
            "REMOTE_INSTALL_KEY": key, "MAX_REQUEST_TIMEOUT": "300",
            "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "*"}


def main():
    pins = json.loads(Path("/scripts/deployed_ce/pins.json").read_text())
    report = identity(Path("/candidate.difypkg"), Path("/plugin"), pins["package_sha256"])
    venv = Path("/runtime/venv")
    if sys.argv[1] == "stage":
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        subprocess.run([str(venv / "bin/python"), "-m", "pip", "install", "--no-index",
                        "--find-links=/wheels", "--only-binary=:all:", "-r", "/plugin/requirements.txt"], check=True)
        trust_ca(venv, Path("/fixture-ca.crt"))
        return
    assert sys.argv[1] == "launch"
    report.update(install_method="remote", entrypoint="python -m main", debug_endpoint="plugin_daemon:5003",
                  fixture_ca_sha256=trust_ca(venv, Path("/fixture-ca.crt")))
    env = launch_environment(Path("/remote-key").read_text())
    Path("/evidence/runtime-identity.json").write_text(json.dumps(report, indent=2) + "\n")
    os.chdir("/plugin")
    os.execve(str(venv / "bin/python"), [str(venv / "bin/python"), "-m", "main"], env)


if __name__ == "__main__":
    main()
