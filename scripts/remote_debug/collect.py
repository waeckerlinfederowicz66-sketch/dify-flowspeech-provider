"""Fail-closed sanitized evidence and project-scoped cleanup for remote debugging."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from scripts.deployed_ce.collect import redact

# Explicitly targeted startup does not enable profiles for later logs/down commands.
COMPOSE = ["docker", "compose", "-f", str(Path(__file__).parent / "compose.yaml"), "--profile", "validation"]
STAGES = ("isolation-initial", "bootstrap", "runtime-identity", "isolation-remote", "connected", "disconnected", "cleanup")
ALLOWED = {name + ".json" for name in STAGES} | {"pins.json", "package-audit.json", "summary.json", "service-logs.txt"}
PRIVATE_STATE = ("remote-key", "fixture.json", "runtime.env", "ca.key")


def secrets(state):
    values = []
    if (state / "fixture.json").exists():
        values.extend(json.loads((state / "fixture.json").read_text()).values())
    if (state / "remote-key").exists():
        values.append((state / "remote-key").read_text().strip())
    if (state / "runtime.env").exists():
        values.extend(line.split("=", 1)[1] for line in (state / "runtime.env").read_text().splitlines()
                      if "=" in line and any(part in line.split("=", 1)[0] for part in ("KEY", "PASSWORD", "SECRET")))
    return [value for value in values if isinstance(value, str) and len(value) >= 8]


def check_evidence(evidence, sensitive):
    for file in evidence.iterdir():
        assert file.name in ALLOWED and file.is_file() and not file.is_symlink(), "Unexpected evidence member"
        text = file.read_text()
        assert not any(value in text for value in sensitive), "Unredacted fixture/debugging credential"
        assert "-----BEGIN" not in text, "Certificate/private key in evidence"
        assert not re.search(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", text), "Unredacted JWT"
        if file.suffix == ".json":
            json.loads(text)


def cleanup(evidence):
    project = os.environ["COMPOSE_PROJECT_NAME"]
    assert re.fullmatch(r"flowspeech-remote-[0-9]+-[0-9]+", project), "Refusing non-job cleanup scope"
    report = {"status": "failed", "compose_profiles": ["validation"]}
    try:
        subprocess.run(COMPOSE + ["down", "--volumes", "--remove-orphans"], check=True,
                       capture_output=True, text=True, timeout=90)
        for resource, command in [("containers", ["ps", "-aq"]), ("networks", ["network", "ls", "-q"]),
                                  ("volumes", ["volume", "ls", "-q"])]:
            result = subprocess.run(["docker", *command, "--filter", "label=com.docker.compose.project=" + project],
                                    check=True, capture_output=True, text=True, timeout=10)
            report[resource + "_remaining"] = len(result.stdout.split())
        leftovers = {name: report[name + "_remaining"] for name in ("containers", "networks", "volumes")}
        assert not any(leftovers.values()), "Project resources remain after cleanup: " + json.dumps(leftovers)
        report["status"] = "passed"
    finally:
        (evidence / "cleanup.json").write_text(json.dumps(report, indent=2) + "\n")


def summary(evidence):
    stages = {}
    for stage in STAGES:
        file = evidence / (stage + ".json")
        stages[stage] = json.loads(file.read_text()).get("status") if file.exists() else "not_run"
    return {"remote_debug_passed": all(value == "passed" for value in stages.values()),
            "cloud_passed": False, "stages": stages,
            "scope": "Supplemental headless CE official TCP remote-debug protocol; independent of full CE gate",
            "limitations": ["No Dify Cloud, browser/UI, production API or public egress-policy validation",
                            "Fixture-only TLS CA in disposable remote Python environment",
                            "Marketplace CE/Cloud checkbox permits documented limitations; no Cloud prerequisite inferred"]}


def main():
    state = Path(os.environ["GATE_STATE"])
    evidence = state / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    mode = sys.argv[1]
    sensitive = secrets(state)
    if mode == "logs":
        result = subprocess.run(COMPOSE + ["logs", "--no-color", "--tail", "300"],
                                check=True, capture_output=True, text=True, timeout=30)
        (evidence / "service-logs.txt").write_text(redact(result.stdout + result.stderr, sensitive))
        check_evidence(evidence, sensitive)
    elif mode == "cleanup":
        cleanup(evidence)
    else:
        assert mode == "finalize"
        try:
            check_evidence(evidence, sensitive)
            report = summary(evidence)
        finally:
            # Containers are already stopped. Remove the job's key and generated credentials even on a leak failure.
            for name in PRIVATE_STATE:
                (state / name).unlink(missing_ok=True)
        report["ephemeral_credential_files_removed"] = True
        (evidence / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
        check_evidence(evidence, sensitive)
        print(json.dumps(report))


if __name__ == "__main__":
    main()
