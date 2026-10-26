"""Add the fixture CA to certifi in the isolated installed plugin, not its code."""
import hashlib
import json
from pathlib import Path
import zipfile


def install_ca():
    ca = Path("/fixture-ca.crt").read_bytes()
    checked = []
    with zipfile.ZipFile("/candidate.difypkg") as archive:
        expected = {name: archive.read(name) for name in archive.namelist() if name.endswith(".py")}
    for manifest in Path("/app/storage/cwd").rglob("manifest.yaml"):
        root = manifest.parent
        if ".venv" in root.parts or not (root / "flowspeech_v1.py").is_file():
            continue
        for name, content in expected.items():
            if (root / name).read_bytes() != content:
                raise RuntimeError("Daemon-installed Python source differs from reviewed package: " + name)
        bundles = list((root / ".venv").glob("lib/python*/site-packages/certifi/cacert.pem"))
        if len(bundles) != 1:
            raise RuntimeError("Expected one certifi bundle in installed plugin environment")
        bundle = bundles[0]
        original = bundle.read_bytes()
        if ca not in original:
            bundle.write_bytes(original + b"\n" + ca)
        checked.append({"python_files_matched": len(expected),
                        "fixture_ca_sha256": hashlib.sha256(ca).hexdigest()})
    if len(checked) != 1:
        raise RuntimeError("Expected exactly one installed FlowSpeech runtime")
    print(json.dumps({"installed_runtime": checked, "plugin_code_changed": False}))


if __name__ == "__main__":
    install_ca()
