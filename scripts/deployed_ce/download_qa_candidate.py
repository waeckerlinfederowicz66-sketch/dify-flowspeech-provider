"""GET one pinned unpublished QA asset; never use tag lookup or change access."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "waeckerlinfederowicz66-sketch/dify-flowspeech-provider"
RELEASE_ID = 426187816
ASSET_ID = 683534668
TAG = "flowspeech-0.2.1-qa-20261027"
SOURCE_SHA = "22c4d7ce1ceba54ba4b0afb2fbd6fcd97dd7642e"
NAME = "flowspeech-0.2.1.difypkg"
SIZE = 128002
SHA256 = "26933a9636a6d77ff940558c3f1cbaf31d89ebaae0148e020a4ba26289886fe6"


def get(endpoint: str, *, binary: bool = False):
    accept = "application/octet-stream" if binary else "application/vnd.github+json"
    try:
        result = subprocess.run(
            ["gh", "api", "--hostname", "github.com", "--method", "GET", endpoint, "--header", "Accept: " + accept],
            env={**os.environ, "GODEBUG": "http2client=0", "GH_PROMPT_DISABLED": "1"},
            capture_output=True, timeout=60 if binary else 30,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("QA GET timed out; stop without retry or fallback") from None
    if result.returncode:
        status = re.search(r"\bHTTP (401|403|404)\b", result.stderr.decode(errors="replace"))
        code = " (HTTP " + status.group(1) + ")" if status else ""
        raise RuntimeError("QA GET failed" + code + "; stop without retry or fallback")
    if binary:
        return result.stdout
    try:
        value = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise RuntimeError("Invalid QA metadata; stop") from None
    if not isinstance(value, dict):
        raise RuntimeError("Invalid QA metadata; stop")
    return value


def verify_asset(asset: dict) -> None:
    expected = {"id": ASSET_ID, "name": NAME, "size": SIZE,
                "digest": "sha256:" + SHA256, "state": "uploaded"}
    if not isinstance(asset, dict) or any(asset.get(key) != value for key, value in expected.items()):
        raise RuntimeError("QA asset metadata mismatch; stop")


def download() -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise RuntimeError("QA repository mismatch; stop")
    if not os.environ.get("GH_TOKEN"):
        raise RuntimeError("Step-scoped GH_TOKEN is required; stop")
    target = ROOT / "dist" / NAME
    if target.exists() or target.is_symlink():
        raise RuntimeError("Refusing to overwrite an existing QA candidate")
    prefix = "repos/" + REPOSITORY + "/releases/"
    release = get(prefix + str(RELEASE_ID))
    if (release.get("id") != RELEASE_ID or release.get("draft") is not True
            or release.get("published_at", "missing") is not None or release.get("tag_name") != TAG
            or release.get("target_commitish") != SOURCE_SHA):
        raise RuntimeError("QA draft release metadata mismatch; stop")
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) != 1:
        raise RuntimeError("QA draft asset inventory mismatch; stop")
    verify_asset(assets[0])
    endpoint = prefix + "assets/" + str(ASSET_ID)
    verify_asset(get(endpoint))
    payload = get(endpoint, binary=True)
    if len(payload) != SIZE or hashlib.sha256(payload).hexdigest() != SHA256:
        raise RuntimeError("QA asset downloaded bytes mismatch; stop")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(payload)
    print(json.dumps({"repository": REPOSITORY, "release_id": RELEASE_ID, "asset_id": ASSET_ID,
                      "draft": True, "tag": TAG, "source_sha": SOURCE_SHA,
                      "name": NAME, "bytes": SIZE, "sha256": SHA256}))


if __name__ == "__main__":
    try:
        download()
    except (RuntimeError, OSError) as error:
        raise SystemExit(str(error)) from None
