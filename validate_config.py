"""Validate raw Docker env-file values without executing or printing secrets."""
from pathlib import Path
from urllib.parse import urlparse

values = {}
for line in Path("collector.env").read_text().splitlines():
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    key, separator, value = line.partition("=")
    if not separator:
        raise SystemExit("Invalid collector.env line; expected KEY=value")
    if key.strip() in values:
        raise SystemExit("Duplicate setting: " + key.strip())
    values[key.strip()] = value
required = ("SENTRA_INGEST_BASE_URL", "SENTRA_WORKSPACE_ID", "SENTRA_COLLECTOR_ID",
            "SENTRA_COLLECTOR_TOKEN", "SENTRA_HOST_ID", "SENTRA_SERVICE_NAME")
for key in required:
    value = values.get(key, "")
    if not value or "REPLACE_" in value:
        raise SystemExit("Provide the issued value for " + key)
u = urlparse(values["SENTRA_INGEST_BASE_URL"])
if u.scheme not in ("https", "http") or not u.hostname or u.hostname.endswith("example.com"):
    raise SystemExit("Provide a reachable Sentra Ingest URL")
try:
    if int(values.get("SENTRA_COLLECTOR_INTERVAL_SECONDS", "10")) < 1:
        raise ValueError
except ValueError:
    raise SystemExit("Collection interval must be a positive integer")
print("Collector identity configuration validated (secret values hidden)")
