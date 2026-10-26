"""Fail before credentials/invocation unless every CE service is network-isolated."""
import hashlib
import json
import os
from pathlib import Path
import subprocess


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True)


def main():
    project = os.environ["COMPOSE_PROJECT_NAME"]
    state = Path(os.environ["GATE_STATE"])
    ids = docker("network", "ls", "--filter", "label=com.docker.compose.project=" + project,
                 "--format", "{{.ID}}").split()
    if len(ids) != 1:
        raise RuntimeError("Expected exactly one project-scoped Docker network")
    networks = json.loads(docker("network", "inspect", *ids))
    if not all(n["Internal"] for n in networks):
        raise RuntimeError("Refusing CE traffic on an externally routed network")
    container_ids = docker("ps", "-aq", "--filter", "label=com.docker.compose.project=" + project).split()
    containers = json.loads(docker("inspect", *container_ids))
    observed = []
    allowed = {n["Name"] for n in networks}
    for container in containers:
        host = container["HostConfig"]
        assert not host["Privileged"] and not host.get("PortBindings")
        assert set(container["NetworkSettings"]["Networks"]) <= allowed
        assert host["NetworkMode"] != "host"
        assert all(m["Destination"] != "/var/run/docker.sock" for m in container["Mounts"])
        observed.append({"service": container["Config"]["Labels"]["com.docker.compose.service"],
                         "image_id": container["Image"], "network_mode": host["NetworkMode"]})
    wheels = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((state / "wheels").glob("*.whl"))}
    assert wheels, "Offline dependency wheelhouse is empty"
    evidence = {"all_networks_internal": True, "no_published_ports": True,
                "containers": observed, "dependency_wheel_sha256": wheels}
    (state / "evidence" / "isolation.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print("Internal-network/no-host-port isolation verified before package installation")


if __name__ == "__main__":
    main()
