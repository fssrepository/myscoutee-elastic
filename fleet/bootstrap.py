#!/usr/bin/env python3
"""Finish the preconfigured Fleet policies after Kibana becomes ready."""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

values = dict(line.split("=", 1) for line in Path(sys.argv[1]).read_text().splitlines())
auth = base64.b64encode(f"elastic:{values['ELASTIC_PASSWORD']}".encode()).decode()
base = "http://127.0.0.1:5602"


def api(path, body=None, method=None):
    headers = {"Authorization": f"Basic {auth}", "kbn-xsrf": "true"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method or ("POST" if body is not None else "GET"),
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


setup = api("/api/fleet/agents/setup", {})
if not setup.get("isInitialized") or setup.get("nonFatalErrors"):
    raise SystemExit("Fleet setup did not complete cleanly")

existing = {item["name"] for item in api("/api/fleet/package_policies").get("items", [])}
for name, package, policy in (
    ("fleet-server-integration", "fleet_server", "fleet-server-policy"),
    ("system-integration", "system", "codeforge-managed-agent"),
):
    if name in existing:
        continue
    package_info = api(f"/api/fleet/epm/packages/{package}")["item"]
    api("/api/fleet/package_policies?format=simplified", {
        "name": name,
        "namespace": "codeforge",
        "package": {"name": package, "version": package_info["version"]},
        "policy_ids": [policy],
        "inputs": {},
    })
print("Fleet policies and integrations are ready")

try:
    api("/api/data_views/data_view/codeforge-fleet-system")
except urllib.error.HTTPError as error:
    if error.code != 404:
        raise
    api("/api/data_views/data_view", {
        "data_view": {
            "id": "codeforge-fleet-system",
            "title": "metrics-system.*",
            "name": "Fleet System metrics",
            "timeFieldName": "@timestamp",
            "allowNoIndex": True,
        },
    })
if api("/api/data_views/default").get("data_view_id") is None:
    api("/api/data_views/default", {"data_view_id": "codeforge-fleet-system"})

data_source = {"type": "data_view_spec", "index_pattern": "metrics-system.*", "time_field": "@timestamp"}


def trend(title, field):
    return {"type": "xy", "title": title, "axis": {},
            "layers": [{"type": "line", "x": {"operation": "date_histogram", "field": "@timestamp"},
                        "y": [{"operation": "average", "field": field,
                               "format": {"type": "percent"}}],
                        "data_source": data_source}],
            "styling": {"fitting": {"type": "none"}}}


def panel(x, y, w, h, config):
    return {"type": "vis", "grid": {"x": x, "y": y, "w": w, "h": h}, "config": config}


dashboard = {
    "title": "CodeForge | Fleet System metrics",
    "description": "System integration data from the managed Fleet agent.",
    "time_range": {"from": "now-24h", "to": "now"},
    "panels": [
        panel(0, 0, 16, 6, {"type": "metric", "title": "System samples",
            "data_source": data_source, "metrics": [{"type": "primary", "operation": "count"}]}),
        panel(16, 0, 16, 6, {"type": "metric", "title": "Average normalized CPU",
            "data_source": data_source, "metrics": [{"type": "primary", "operation": "average",
            "field": "system.cpu.total.norm.pct", "format": {"type": "percent"}}]}),
        panel(32, 0, 16, 6, {"type": "metric", "title": "Average used memory",
            "data_source": data_source, "metrics": [{"type": "primary", "operation": "average",
            "field": "system.memory.used.pct", "format": {"type": "percent"}}]}),
        panel(0, 6, 24, 13, trend("CPU load over time", "system.cpu.total.norm.pct")),
        panel(24, 6, 24, 13, trend("Memory use over time", "system.memory.used.pct")),
        panel(0, 19, 48, 12, {"type": "xy", "title": "Samples by System dataset", "axis": {},
            "layers": [{"type": "bar_horizontal", "x": {"operation": "terms",
                        "fields": ["data_stream.dataset"], "limit": 12},
                        "y": [{"operation": "count"}], "data_source": data_source}]}),
    ],
}
for number, item in enumerate(dashboard["panels"]):
    visualization_id = f"codeforge-fleet-system-visual-{number + 1:02d}"
    api(f"/api/visualizations/{visualization_id}", item["config"], method="PUT")
    item["config"] = {"ref_id": visualization_id}
api("/api/dashboards/codeforge-fleet-system", dashboard, method="PUT")
print("Fleet System metrics dashboard and 6 library visualizations are ready")

if not values.get("FLEET_ENROLLMENT_TOKEN"):
    key = api("/api/fleet/enrollment_api_keys", {
        "name": "codeforge-managed-agent-token",
        "policy_id": "codeforge-managed-agent",
    })["item"]
    credential_file = Path(sys.argv[1])
    lines = credential_file.read_text().splitlines()
    lines.append("FLEET_ENROLLMENT_TOKEN=" + key["api_key"])
    credential_file.write_text("\n".join(lines) + "\n")
