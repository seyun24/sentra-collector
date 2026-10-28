"""Parse raw settings and generate read-only input mounts. Never executes env values."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse


def generate(env_path, output):
    values = {}
    for line in Path(env_path).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or key in values:
            raise ValueError("Invalid or duplicate setting: " + key)
        values[key] = value
    for key in ("SENTRA_INGEST_BASE_URL", "SENTRA_WORKSPACE_ID", "SENTRA_COLLECTOR_ID",
                "SENTRA_COLLECTOR_TOKEN", "SENTRA_HOST_ID", "SENTRA_SERVICE_NAME"):
        if not values.get(key) or "REPLACE_" in values[key]:
            raise ValueError("Provide the issued value for " + key)
    url = urlparse(values["SENTRA_INGEST_BASE_URL"])
    if url.scheme not in ("https", "http") or not url.hostname or url.hostname.endswith("example.com"):
        raise ValueError("Provide a reachable Sentra Ingest URL")
    if int(values.get("SENTRA_COLLECTOR_INTERVAL_SECONDS", "10")) < 1:
        raise ValueError("Collection interval must be positive")
    service = {
        "image": os.environ.get("COLLECTOR_IMAGE", "ghcr.io/seyun24/sentra-collector:v0.1.0"),
        "env_file": [{"path": str(Path(env_path).resolve()), "format": "raw"}],
        "environment": {
            "SENTRA_COLLECTOR_DEV_MODE": "false", "SENTRA_COLLECTOR_EXEC_ENABLED": "false",
            "SENTRA_COLLECTOR_LOG_STATE_PATH": "/var/lib/sentra/state/log.json",
            "SENTRA_COLLECTOR_TRACE_STATE_PATH": "/var/lib/sentra/state/trace.json",
            # Missing host root deliberately disables disk metrics in v0.1.0.
            "SENTRA_COLLECTOR_HOST_ROOT": "/sentra-unmounted-host", "PYTHONUNBUFFERED": "1"},
        "restart": "unless-stopped", "read_only": True, "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"], "tmpfs": ["/tmp:size=32m"],
        "volumes": [{"type": "volume", "source": "collector-state", "target": "/var/lib/sentra/state"}],
        "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}}}
    mode = values.get("SENTRA_INSTALL_HOST_METRICS", "true").lower()
    if mode not in ("true", "false"):
        raise ValueError("SENTRA_INSTALL_HOST_METRICS must be true or false")
    if mode == "true":
        service.update(pid="host", network_mode="host")
    directories = {}
    def mount_file(raw):
        if not raw or not Path(raw).is_absolute():
            raise ValueError("Collection file paths must be absolute")
        path = Path(raw).resolve()
        parent = path.parent
        if not parent.is_dir() or path.is_dir():
            raise ValueError("Collection file parent must exist and input must not be a directory: " + raw)
        if parent == Path("/") or any(path == Path(x) or Path(x) in path.parents for x in ("/proc", "/sys", "/dev")):
            raise ValueError("Use an application log directory, not root or system pseudo-filesystems")
        if parent not in directories:
            target = "/inputs/" + str(len(directories))
            directories[parent] = target
            service["volumes"].append({"type": "bind", "source": str(parent), "target": target,
                                       "read_only": True, "bind": {"create_host_path": False}})
        return directories[parent] + "/" + path.name
    logs = []
    for entry in values.get("SENTRA_COLLECTOR_LOG_SOURCES", "").split(","):
        if not entry.strip():
            continue
        parts = entry.strip().rsplit(":", 2)
        logs.append(":".join([mount_file(parts[0]), *parts[1:]]))
    service["environment"]["SENTRA_COLLECTOR_LOG_SOURCES"] = ",".join(logs)
    for key in ("SENTRA_COLLECTOR_TRACE_JSONL_PATH", "SENTRA_COLLECTOR_DB_SQLITE_PATH"):
        raw = values.get(key, "")
        service["environment"][key] = mount_file(raw) if raw else ""
    target = Path(output)
    temporary = target.with_suffix(".tmp")
    def escape(value):
        if isinstance(value, str):
            return value.replace("$", "$$")
        if isinstance(value, list):
            return [escape(item) for item in value]
        if isinstance(value, dict):
            return {key: escape(item) for key, item in value.items()}
        return value
    temporary.write_text(json.dumps(escape({"name": "sentra-collector", "services": {"collector": service},
                                           "volumes": {"collector-state": {}}}), indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(target)
    print("Configuration valid; read-only input directories: " + str(len(directories)))
    print("Host process/network access: " + mode + "; host root is not mounted; disk metrics disabled")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default="collector.env")
    parser.add_argument("--output", default="compose.generated.json")
    args = parser.parse_args()
    try:
        generate(args.env_file, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
