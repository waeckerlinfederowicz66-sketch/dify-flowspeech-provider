"""Fail before credentials/invocation unless every CE service is network-isolated."""
import hashlib
import json
import os
from pathlib import Path
import subprocess


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True)


def validate_container(container, allowed):
    service = container["Config"]["Labels"]["com.docker.compose.service"]
    host = container["HostConfig"]
    settings = container["NetworkSettings"]
    attached = settings["Networks"]

    def refuse(reason):
        raise RuntimeError(f"{service}: {reason}")

    if host["Privileged"] or host.get("PortBindings"):
        refuse("privileged container or published host ports")
    if any(m["Destination"] == "/var/run/docker.sock" for m in container["Mounts"]):
        refuse("Docker socket mounted")
    if host["NetworkMode"] == "none":
        # Docker may retain a 'none' endpoint even after the init container exits.
        if set(attached) - {"none"}:
            refuse("network-disabled container has another network attached")
        route_fields = ("IPAddress", "Gateway", "GlobalIPv6Address", "IPv6Gateway",
                        "IPPrefixLen", "GlobalIPv6PrefixLen")
        if any(endpoint.get(field) for endpoint in [settings, *attached.values()]
               for field in route_fields):
            refuse("network-disabled container has an IP address or route")
    elif host["NetworkMode"] not in allowed or set(attached) != {host["NetworkMode"]}:
        refuse("container must use only the project internal network or network mode none")


def main():
    project = os.environ["COMPOSE_PROJECT_NAME"]
    state = Path(os.environ["GATE_STATE"])
    evidence = {"status": "failed", "containers": []}
    output = state / "evidence" / "isolation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        ids = docker("network", "ls", "--filter", "label=com.docker.compose.project=" + project,
                     "--format", "{{.ID}}").split()
        if len(ids) != 1:
            raise RuntimeError("Expected exactly one project-scoped Docker network")
        networks = json.loads(docker("network", "inspect", *ids))
        if len(networks) != 1 or networks[0]["Internal"] is not True:
            raise RuntimeError("Refusing CE traffic on an externally routed network")
        evidence["all_networks_internal"] = True
        container_ids = docker("ps", "-aq", "--filter", "label=com.docker.compose.project=" + project).split()
        if not container_ids:
            raise RuntimeError("No project containers found")
        containers = json.loads(docker("inspect", *container_ids))
        if not containers:
            raise RuntimeError("No project containers inspected")
        evidence["containers"] = [
            {"service": c["Config"]["Labels"]["com.docker.compose.service"],
             "image_id": c["Image"], "network_mode": c["HostConfig"]["NetworkMode"],
             "attached_networks": sorted(c["NetworkSettings"]["Networks"])} for c in containers]
        allowed = {n["Name"] for n in networks}
        for container in containers:
            validate_container(container, allowed)
        evidence["no_published_ports"] = True
        wheels = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((state / "wheels").glob("*.whl"))}
        if not wheels:
            raise RuntimeError("Offline dependency wheelhouse is empty")
        evidence.update(status="passed", dependency_wheel_sha256=wheels)
    except RuntimeError as error:
        evidence["error"] = str(error)
        raise
    finally:
        output.write_text(json.dumps(evidence, indent=2) + "\n")
    print("Internal-network/no-host-port isolation verified before package installation")


if __name__ == "__main__":
    main()
