"""Retain bounded, redacted CE diagnostics, never settings, certificates or cookies."""
import json
import os
from pathlib import Path
import re
import subprocess


def redact(text: str, sensitive: list[str]) -> str:
    for value in sorted(set(sensitive), key=len, reverse=True):
        if len(value) >= 8:
            text = text.replace(value, "[fixture-redacted]")
    text = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[jwt-redacted]", text)
    text = re.sub(r"(?i)(authorization|cookie|set-cookie)(\s*[:=]\s*)[^\n]+", r"\1\2[redacted]", text)
    return text[-250_000:]


def main():
    state = Path(os.environ["GATE_STATE"])
    evidence = state / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    sensitive = []
    fixture = state / "fixture.json"
    if fixture.exists():
        sensitive.extend(json.loads(fixture.read_text()).values())
    settings = state / "runtime.env"
    if settings.exists():
        sensitive.extend(line.split("=", 1)[1] for line in settings.read_text().splitlines()
                         if "=" in line and any(key in line.split("=", 1)[0] for key in ("KEY", "PASSWORD", "SECRET")))
    compose = ["docker", "compose", "-f", str(Path(__file__).parent / "compose.yaml")]
    result = subprocess.run(compose + ["logs", "--no-color", "--tail", "300"],
                            capture_output=True, text=True, timeout=30)
    (evidence / "service-logs.txt").write_text(redact(result.stdout + result.stderr, sensitive))
    report = {"ce_passed": False, "cloud_passed": False, "stages": {}}
    for stage in ("install", "run", "short-host"):
        file = evidence / (stage + ".json")
        report["stages"][stage] = json.loads(file.read_text()).get("status") if file.exists() else "not_run"
    report["ce_passed"] = all(value == "passed" for value in report["stages"].values())
    report["scope"] = "Headless CE console workflow through real API, worker and local Go plugin daemon"
    report["limitations"] = ["Dify Cloud not installed or tested", "No production FlowSpeech requests",
                             "Fixture CA added only to isolated runtime trust bundle",
                             "Unsigned candidate installed with verification disabled only in disposable CE",
                             "No browser/UI, external reverse proxy or Cloud egress policy validation"]
    (evidence / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    # Only this allowlisted directory is uploaded. Stop if any raw fixture secret escaped.
    for file in evidence.iterdir():
        if file.is_file():
            text = file.read_text(errors="replace")
            cleaned = redact(text, sensitive) if file.name == "service-logs.txt" else text
            assert not any(value in cleaned for value in sensitive if len(value) >= 8), file.name
    print(json.dumps(report))


if __name__ == "__main__":
    main()
