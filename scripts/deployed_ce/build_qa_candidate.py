"""Build from committed inputs; accept only the already-reviewed package bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
CLI_VERSION = "v0.6.12"
CLI_URL = "https://github.com/langgenius/dify-plugin-daemon/releases/download/0.6.12/dify-plugin-linux-amd64"
CLI_SHA256 = "f5190893643492c3f17f12c9752615a5652e47bbf30e84298634e176611aa108"
PACKAGE_SHA256 = "523701c995e653e66fdc357077a13bc1ce337a115efe54e371975046857284f2"
PACKAGE_SIZE = 127641
MEMBER_COUNT = 17


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(args: list[str], cwd: Path, env: dict[str, str], timeout: int) -> str:
    try:
        result = subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("Independent build command unavailable or timed out") from None
    if result.returncode:
        raise RuntimeError("Independent build command failed; stop without fallback")
    return result.stdout.strip()


def safe_path(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or str(path) != name.rstrip("/"):
        raise RuntimeError("Unsafe export/member path")


def export_source(archive: Path, source: Path) -> None:
    with tarfile.open(archive, "r:") as bundle:
        members = bundle.getmembers()
        if len({item.name for item in members}) != len(members):
            raise RuntimeError("Duplicate export path")
        for item in members:
            safe_path(item.name)
            if not (item.isfile() or item.isdir()):
                raise RuntimeError("Export must contain only regular files and directories")
        bundle.extractall(source, members=members, filter="data")


def verify_inputs(source: Path, pins: dict) -> None:
    members = pins["members"]
    names = [item["path"] for item in members]
    if len(names) != MEMBER_COUNT or names != sorted(set(names)):
        raise RuntimeError("Expected exactly 17 distinct sorted input pins")
    for item in members + [pins["source_filter"]]:
        safe_path(item["path"])
        target = source / item["path"]
        if target.is_symlink() or not target.is_file():
            raise RuntimeError("Missing or nonregular reviewed input")
        data = target.read_bytes()
        if len(data) != item["bytes"] or digest(data) != item["sha256"]:
            raise RuntimeError("Reviewed source input hash/size mismatch")


def verify_package(candidate: Path, pins: dict) -> None:
    if candidate.is_symlink() or not candidate.is_file():
        raise RuntimeError("Independent package output missing or nonregular")
    data = candidate.read_bytes()
    if len(data) != PACKAGE_SIZE or digest(data) != PACKAGE_SHA256:
        raise RuntimeError("Independent package differs from frozen size/SHA-256; stop")
    with zipfile.ZipFile(candidate) as bundle:
        if bundle.namelist() != [item["path"] for item in pins["members"]]:
            raise RuntimeError("Independent package member inventory mismatch")
        for item in pins["members"]:
            member = bundle.read(item["path"])
            if len(member) != item["bytes"] or digest(member) != item["sha256"]:
                raise RuntimeError("Independent package member hash/size mismatch")


def cli_provenance(data: bytes) -> dict:
    """Read inline Go build information without running the downloaded ELF."""
    offset = data.find(bytes.fromhex("ff20476f206275696c64696e663a"))
    if offset < 0 or len(data) < offset + 32 or not data[offset + 15] & 2:
        raise RuntimeError("Official CLI inline Go build information missing")

    def read_string(position: int) -> tuple[bytes, int]:
        size = 0
        for shift in range(0, 70, 7):
            if position >= len(data):
                break
            value = data[position]
            position += 1
            size |= (value & 127) << shift
            if value < 128:
                if size > 65536 or position + size > len(data):
                    break
                return data[position:position + size], position + size
        raise RuntimeError("Invalid official CLI Go build information")

    version, position = read_string(offset + 32)
    module, _ = read_string(position)
    text = module[16:-16].decode("utf-8") if len(module) >= 32 else ""
    settings = dict(line[6:].split("=", 1) for line in text.splitlines()
                    if line.startswith("build\t") and "=" in line[6:])
    if settings.get("GOOS") != "linux" or settings.get("GOARCH") != "amd64":
        raise RuntimeError("Official CLI Go target mismatch")
    return {"go_version": version.decode("ascii"),
            "main_package": next((line[5:] for line in text.splitlines() if line.startswith("path\t")), None),
            "go_target": "linux/amd64", "vcs_revision": settings.get("vcs.revision"),
            "vcs_modified": settings.get("vcs.modified")}


def build(work: Path) -> dict:
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        raise RuntimeError("Linux AMD64 only; never execute this ELF on Darwin")
    work = work.absolute()
    # Nothing may be written into the checkout or a reused state directory.
    if work.is_symlink() or work.resolve().is_relative_to(ROOT.resolve()):
        raise RuntimeError("Build workspace must be outside the source checkout")
    try:
        work.mkdir(parents=True, exist_ok=False, mode=0o700)
    except FileExistsError:
        raise RuntimeError("Refuse to overwrite an existing build workspace") from None
    home, temporary, source = [work / name for name in ("home", "tmp", "source")]
    for directory in (home, temporary, source):
        directory.mkdir(mode=0o700)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(temporary),
           "LC_ALL": "C", "TZ": "UTC", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0"}
    pins = json.loads((ROOT / "scripts/deployed_ce/build-inputs.json").read_text())
    head = run(["git", "rev-parse", "HEAD"], ROOT, env, 10)
    if not re.fullmatch(r"[0-9a-f]{40}", head) or os.environ.get("GITHUB_SHA", head) != head:
        raise RuntimeError("Checked-out commit does not match workflow source")
    archive = work / "source.tar"
    run(["git", "archive", "--format=tar", "--output=" + str(archive), head], ROOT, env, 30)
    export_source(archive, source)
    verify_inputs(source, pins)
    cli = work / "dify-plugin-linux-amd64"
    run(["curl", "--disable", "--http1.1", "--fail", "--silent", "--show-error",
         "--location", "--proto", "=https", "--proto-redir", "=https",
         "--connect-timeout", "10", "--max-time", "120", "--max-filesize", "104857600",
         "--output", str(cli), CLI_URL], work, env, 130)
    data = cli.read_bytes()
    if digest(data) != CLI_SHA256:
        raise RuntimeError("Official CLI SHA-256 mismatch; never execute")
    if data[:6] != b"\x7fELF\x02\x01" or data[18:20] != b"\x3e\x00":
        raise RuntimeError("Expected Linux AMD64 ELF")
    provenance = cli_provenance(data)
    cli.chmod(0o700)
    version = run([str(cli), "version"], work, env, 10)
    if version != CLI_VERSION:
        raise RuntimeError("Official CLI runtime version mismatch")
    candidate = work / "candidate.difypkg"
    run([str(cli), "plugin", "package", ".", "-o", str(candidate)], source, env, 60)
    verify_package(candidate, pins)
    report = {"source_commit": head, "cli_url": CLI_URL, "cli_sha256": CLI_SHA256,
              "cli_version": version, "cli_build_provenance": provenance,
              "package_sha256": PACKAGE_SHA256,
              "package_bytes": PACKAGE_SIZE, "members": pins["members"],
              "source_filter": pins["source_filter"], "acquisition_credentials": False}
    (work / "build-proof.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("work", type=Path)
    build(parser.parse_args().work)
