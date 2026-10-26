"""Prepare a fresh remote-only CE fixture from the immutable reviewed archive."""
import json
from pathlib import Path
import sys
import zipfile

from scripts.deployed_ce.prepare import prepare as prepare_ce
from scripts.verify_artifacts import inspect


def prepare(state: Path):
    prepare_ce(state)
    audit = inspect(state / "candidate.difypkg")
    (state / "evidence/package-audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    settings = dict(line.split("=", 1) for line in (state / "runtime.env").read_text().splitlines())
    settings.update(PLUGIN_REMOTE_INSTALLING_ENABLED="true", PLUGIN_REMOTE_INSTALLING_HOST="0.0.0.0",
                    PLUGIN_REMOTE_INSTALLING_PORT="5003", PLUGIN_REMOTE_INSTALL_HOST="plugin_daemon",
                    PLUGIN_REMOTE_INSTALL_PORT="5003", PLUGIN_REMOTE_INSTALLING_MAX_CONN="2",
                    PLUGIN_REMOTE_INSTALLING_MAX_SINGLE_TENANT_CONN="1",
                    PLUGIN_REMOTE_INSTALL_SERVER_EVENT_LOOP_NUMS="1")
    (state / "runtime.env").write_text("".join(f"{k}={v}\n" for k, v in settings.items()))
    # Not an env_file: the key is read inside the disposable process, never a shell argument.
    (state / "remote-key").write_text("")
    root = state / "plugin"
    root.mkdir()
    with zipfile.ZipFile(state / "candidate.difypkg") as archive:
        if len(set(archive.namelist())) != len(archive.namelist()):
            raise ValueError("Duplicate archive members")
        archive.extractall(root)


if __name__ == "__main__":
    prepare(Path(sys.argv[1]).resolve())
