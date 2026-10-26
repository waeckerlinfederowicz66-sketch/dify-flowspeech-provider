"""Retain both isolation checks without altering the established CE guard."""
import json
import os
from pathlib import Path
import sys

from scripts.deployed_ce import check_isolation


def main():
    stage = sys.argv[1]
    assert stage in {"initial", "remote"}
    evidence = Path(os.environ["GATE_STATE"]) / "evidence"
    try:
        check_isolation.main()
        if stage == "remote":
            project = os.environ["COMPOSE_PROJECT_NAME"]
            ids = check_isolation.docker("ps", "-q", "--filter", "label=com.docker.compose.project=" + project,
                                        "--filter", "label=com.docker.compose.service=remote_plugin").split()
            assert len(ids) == 1, "Exactly one running remote process is required"
    except Exception:
        file = evidence / "isolation.json"
        if file.exists():
            report = json.loads(file.read_text())
            report["status"] = "failed"
            file.write_text(json.dumps(report, indent=2) + "\n")
        raise
    finally:
        if (evidence / "isolation.json").exists():
            (evidence / "isolation.json").rename(evidence / ("isolation-" + stage + ".json"))


if __name__ == "__main__":
    main()
