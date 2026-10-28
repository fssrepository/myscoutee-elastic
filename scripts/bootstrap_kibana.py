#!/usr/bin/env python3
"""Create the lab's Discover data views and ready-to-use dashboards."""

import json
import os
import base64
import time
import urllib.error
import urllib.request


BASE = os.environ.get("KIBANA_URL", "http://127.0.0.1:5601").rstrip("/")
VIEWS = (
    ("codeforge-findings", "forge-findings", "indexed_at"),
    ("codeforge-files", "forge-files", "indexed_at"),
    ("codeforge-activity", "forge-activity", "@timestamp"),
    ("codeforge-metricbeat", "metricbeat-*", "@timestamp"),
    ("codeforge-heartbeat", "heartbeat-*", "@timestamp"),
    ("codeforge-agent", "metrics-system.*", "@timestamp"),
    ("codeforge-auditbeat", "auditbeat-*", "@timestamp"),
    ("codeforge-packetbeat", "packetbeat-*", "@timestamp"),
    ("codeforge-demo-offerings", "demo-myscoutee-offerings", "@timestamp"),
    ("codeforge-demo-events", "demo-myscoutee-events", "@timestamp"),
    ("codeforge-demo-endpoint", "demo-myscoutee-endpoint", "@timestamp"),
)


def api(path, body=None, method=None):
    credentials = f"{os.environ.get('KIBANA_USERNAME', 'elastic')}:{os.environ['KIBANA_PASSWORD']}"
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method or ("POST" if body is not None else "GET"),
        headers={"kbn-xsrf": "true", "Content-Type": "application/json",
                 "Authorization": "Basic " + base64.b64encode(credentials.encode()).decode()},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


for _ in range(180):
    try:
        if api("/api/status").get("status", {}).get("overall", {}).get("level") == "available":
            break
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        pass
    time.sleep(2)
else:
    raise SystemExit("Kibana did not become available")

created = 0
for identifier, title, time_field in VIEWS:
    try:
        api(f"/api/data_views/data_view/{identifier}")
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        api("/api/data_views/data_view", {
            "data_view": {
                "id": identifier,
                "title": title,
                "name": title,
                "timeFieldName": time_field,
                "allowNoIndex": True,
            },
        })
        created += 1

if api("/api/data_views/default").get("data_view_id") is None:
    api("/api/data_views/default", {"data_view_id": "codeforge-findings"})


def source(pattern, field):
    return {"type": "data_view_spec", "index_pattern": pattern, "time_field": field}


def panel(x, y, w, h, config):
    return {"type": "vis", "grid": {"x": x, "y": y, "w": w, "h": h}, "config": config}


def metric(title, pattern, field, label):
    return {"type": "metric", "title": title, "data_source": source(pattern, field),
            "metrics": [{"type": "primary", "operation": "count", "label": label}]}


def bar(title, pattern, time_field, category):
    return {"type": "xy", "title": title, "axis": {}, "legend": {"visibility": "hidden"},
            "layers": [{"type": "bar_horizontal", "x": {"operation": "terms", "fields": [category],
                        "limit": 12, "rank_by": {"type": "metric", "metric_index": 0, "direction": "desc"}},
                        "y": [{"operation": "count", "label": "Records"}],
                        "data_source": source(pattern, time_field)}]}


def line(title, pattern, time_field, category=None):
    layer = {"type": "line", "x": {"operation": "date_histogram", "field": time_field},
             "y": [{"operation": "count", "label": "Events"}],
             "data_source": source(pattern, time_field)}
    if category:
        layer["breakdown_by"] = {"operation": "terms", "fields": [category], "limit": 4,
                                 "rank_by": {"type": "alphabetical", "direction": "asc"}}
    return {"type": "xy", "title": title, "axis": {}, "legend": {"visibility": "auto"},
            "layers": [layer], "styling": {"fitting": {"type": "none"}}}


dashboard_definitions = {
    "codeforge-findings-overview": {
        "title": "CodeForge | Findings overview",
        "description": "MyScoutee source review: hotspots, rules, severity and review status.",
        "time_range": {"from": "now-30d", "to": "now"},
        "panels": [
            panel(0, 0, 12, 6, metric("Findings", "forge-findings", "indexed_at", "Findings")),
            panel(12, 0, 12, 6, metric("Files", "forge-files", "indexed_at", "Files")),
            panel(24, 0, 24, 6, {"type": "pie", "title": "Findings by severity",
                "data_source": source("forge-findings", "indexed_at"),
                "metrics": [{"operation": "count"}],
                "group_by": [{"operation": "terms", "fields": ["severity"], "limit": 5}]}),
            panel(0, 6, 48, 15, {"type": "heatmap", "title": "Hotspots: module × rule",
                "data_source": source("forge-findings", "indexed_at"),
                "axis": {"x": {"scale": "ordinal"}, "y": {}},
                "x": {"operation": "terms", "fields": ["module"], "limit": 12},
                "y": {"operation": "terms", "fields": ["rule"], "limit": 8},
                "metric": {"operation": "count", "empty_as_null": True}}),
            panel(0, 21, 24, 13, bar("Findings by module", "forge-findings", "indexed_at", "module")),
            panel(24, 21, 24, 13, bar("Review decisions", "forge-findings", "indexed_at", "status")),
        ],
    },
    "codeforge-stack-telemetry": {
        "title": "CodeForge | Stack telemetry",
        "description": "Filebeat/Logstash activity, Heartbeat checks and Elasticsearch metrics.",
        "time_range": {"from": "now-24h", "to": "now"},
        "panels": [
            panel(0, 0, 16, 6, metric("Activity events", "forge-activity", "@timestamp", "Events")),
            panel(16, 0, 16, 6, metric("HTTP checks", "heartbeat-*", "@timestamp", "Checks")),
            panel(32, 0, 16, 6, metric("Metric samples", "metricbeat-*", "@timestamp", "Samples")),
            panel(0, 6, 24, 13, line("CodeForge activity over time", "forge-activity", "@timestamp")),
            panel(24, 6, 24, 13, line("HTTP checks over time", "heartbeat-*", "@timestamp", "monitor.name")),
            panel(0, 19, 24, 13, bar("Checks by monitor", "heartbeat-*", "@timestamp", "monitor.name")),
            panel(24, 19, 24, 13, bar("Metric datasets", "metricbeat-*", "@timestamp", "event.dataset")),
        ],
    },
    "codeforge-demo-offerings": {
        "title": "MyScoutee demo | Service discovery",
        "description": "Fictional MyScoutee offerings: category, city and publication filters. No live product data.",
        "time_range": {"from": "now-30d", "to": "now"},
        "panels": [
            panel(0, 0, 24, 6, metric("Fictional offerings", "demo-myscoutee-offerings", "@timestamp", "Offerings")),
            panel(24, 0, 24, 6, {"type": "metric", "title": "Average listed price (EUR)",
                "data_source": source("demo-myscoutee-offerings", "@timestamp"),
                "metrics": [{"type": "primary", "operation": "average", "field": "price_eur"}]}),
            panel(0, 6, 24, 14, bar("Offerings by category", "demo-myscoutee-offerings", "@timestamp", "category")),
            panel(24, 6, 24, 14, bar("Offerings by city", "demo-myscoutee-offerings", "@timestamp", "city")),
            panel(0, 20, 24, 13, bar("Publication status", "demo-myscoutee-offerings", "@timestamp", "status")),
            panel(24, 20, 24, 13, bar("Listing language", "demo-myscoutee-offerings", "@timestamp", "language")),
        ],
    },
    "codeforge-demo-reliability": {
        "title": "MyScoutee demo | Event reliability",
        "description": "Synthetic outbox deliveries and ticket check-in replay outcomes; no live backend connection.",
        "time_range": {"from": "now-24h", "to": "now"},
        "panels": [
            panel(0, 0, 24, 6, metric("Synthetic events", "demo-myscoutee-events", "@timestamp", "Events")),
            panel(24, 0, 24, 6, {"type": "metric", "title": "Average processing time (ms)",
                "data_source": source("demo-myscoutee-events", "@timestamp"),
                "metrics": [{"type": "primary", "operation": "average", "field": "latency_ms"}]}),
            panel(0, 6, 48, 14, line("Service events over time", "demo-myscoutee-events", "@timestamp", "event.dataset")),
            panel(0, 20, 24, 13, bar("Event outcomes", "demo-myscoutee-events", "@timestamp", "event.outcome")),
            panel(24, 20, 24, 13, bar("Actions", "demo-myscoutee-events", "@timestamp", "event.action")),
        ],
    },
}
for identifier, definition in dashboard_definitions.items():
    for number, item in enumerate(definition["panels"]):
        visualization_id = f"{identifier}-visual-{number + 1:02d}"
        api(f"/api/visualizations/{visualization_id}", item["config"], method="PUT")
        item["config"] = {"ref_id": visualization_id}
    api(f"/api/dashboards/{identifier}", definition, method="PUT")

def saved_object(kind, identifier, attributes, references=()):
    return api(f"/api/saved_objects/{kind}/{identifier}?overwrite=true",
               {"attributes": attributes, "references": list(references)}, method="POST")


for identifier, title, description, view, query, columns in (
    ("codeforge-demo-published-offerings", "MyScoutee demo | Published offerings",
     "Fictional listings inspired by the MyScoutee service categories.",
     "codeforge-demo-offerings", "status: published",
     ["title", "category", "city", "language", "price_eur", "rating"]),
    ("codeforge-demo-retry-events", "MyScoutee demo | Retries and replay failures",
     "Synthetic outbox and ticket check-in failure events.",
     "codeforge-demo-events", "event.outcome: failure",
     ["@timestamp", "event.dataset", "event.action", "message", "attempts", "latency_ms"]),
    ("codeforge-demo-endpoint-signals", "MyScoutee demo | Endpoint signals",
     "Synthetic endpoint-shaped signals, not telemetry from protected hosts.",
     "codeforge-demo-endpoint", "demo: true",
     ["@timestamp", "event.action", "host.name", "host.os.type", "user.name", "message"]),
):
    saved_object("search", identifier, {
        "title": title, "description": description,
        "tabs": [{"id": "results", "label": "Results", "attributes": {
            "columns": columns, "sort": [["@timestamp", "desc"]],
            "grid": {}, "hideChart": False, "isTextBasedQuery": False,
            "timeRestore": True, "timeRange": {"from": "now-30d", "to": "now"},
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({
                "query": {"query": query, "language": "kuery"}, "filter": [],
                "indexRefName": "tab_results.kibanaSavedObjectMeta.searchSourceJSON.index",
            })},
        }}],
        "timeRestore": True, "timeRange": {"from": "now-30d", "to": "now"},
    }, [{"type": "index-pattern", "id": view,
         "name": "tab_results.kibanaSavedObjectMeta.searchSourceJSON.index"}])

basemap = {
    "id": "codeforge-basemap", "type": "EMS_VECTOR_TILE", "label": "Basemap",
    "sourceDescriptor": {"type": "EMS_TMS", "isAutoSelect": True,
                         "lightModeDefault": "road_map_desaturated_v9"},
    "minZoom": 0, "maxZoom": 24, "alpha": 1, "visible": True,
    "style": {"type": "EMS_VECTOR_TILE", "color": ""}, "includeInFitToBounds": True,
}
offerings_layer = {
    "id": "codeforge-offerings-layer", "type": "MVT_VECTOR",
    "label": "Fictional service offerings", "minZoom": 0, "maxZoom": 24,
    "alpha": 0.85, "visible": True, "includeInFitToBounds": True,
    "sourceDescriptor": {
        "type": "ES_SEARCH", "id": "codeforge-offerings-source",
        "geoField": "location", "scalingType": "MVT",
        "indexPatternRefName": "layer_1_source_index_pattern",
        "applyGlobalQuery": True, "applyGlobalTime": True,
        "applyForceRefresh": True, "filterByMapBounds": True,
        "tooltipProperties": ["title", "category", "city", "price_eur", "status"],
        "sortField": "", "sortOrder": "desc", "topHitsGroupByTimeseries": False,
        "topHitsSplitField": "", "topHitsSize": 1,
    },
    "style": {"type": "VECTOR", "properties": {
        "icon": {"type": "STATIC", "options": {"value": "marker"}},
        "fillColor": {"type": "STATIC", "options": {"color": "#16BFC0"}},
        "lineColor": {"type": "STATIC", "options": {"color": "#087E80"}},
        "lineWidth": {"type": "STATIC", "options": {"size": 1}},
        "iconSize": {"type": "STATIC", "options": {"size": 14}},
        "iconOrientation": {"type": "STATIC", "options": {"orientation": 0}},
        "labelText": {"type": "STATIC", "options": {"value": ""}},
        "labelColor": {"type": "STATIC", "options": {"color": "#183047"}},
        "labelSize": {"type": "STATIC", "options": {"size": 12}},
        "symbolizeAs": {"options": {"value": "circle"}},
    }, "isTimeAware": True,
    },
    "joins": [], "disableTooltips": False,
}
saved_object("map", "codeforge-demo-offerings-map", {
    "title": "MyScoutee demo | Service offering map",
    "description": "Fictional listings at example city coordinates. No live user locations.",
    "layerListJSON": json.dumps([basemap, offerings_layer]),
    "mapStateJSON": json.dumps({
        "zoom": 5.0, "center": {"lon": 17.3, "lat": 48.7},
        "timeFilters": {"from": "now-30d", "to": "now"},
        "refreshConfig": {"isPaused": True, "interval": 0},
        "query": {"language": "kuery", "query": "status: published"},
        "filters": [], "settings": {
            "initialLocation": "LAST_SAVED_LOCATION", "autoFitToDataBounds": False,
            "fixedLocation": {"lat": 48.7, "lon": 17.3, "zoom": 5},
            "browserLocation": {"zoom": 5}, "maxZoom": 24, "minZoom": 0,
            "showSpatialFilters": True,
        },
    }),
    "uiStateJSON": json.dumps({"isLayerTOCOpen": True, "openTOCDetails": []}),
}, [{"type": "index-pattern", "id": "codeforge-demo-offerings",
     "name": "layer_1_source_index_pattern"}])

# An example Security detection rule over synthetic audit events. No connectors or
# external actions are configured, so all alerts stay in this local Kibana.
rule_id = "codeforge-demo-ticket-replay"
try:
    api(f"/api/detection_engine/rules?rule_id={rule_id}")
except urllib.error.HTTPError as error:
    if error.code != 404:
        raise
    api("/api/detection_engine/rules", {
        "rule_id": rule_id, "name": "MyScoutee demo | Ticket replay failures",
        "description": "Synthetic ticket check-in replay failures in the local lab. No live MyScoutee data or notifications.",
        "type": "query", "language": "kuery",
        "query": 'event.action: "ticket.checkin.replay" and event.outcome: "failure"',
        "index": ["demo-myscoutee-events"],
        "severity": "low", "risk_score": 21,
        "tags": ["MyScoutee demo", "synthetic"],
        "interval": "1m", "from": "now-15m", "enabled": True,
    })

def mitre(tactic_id, tactic_name, technique_id, technique_name):
    return [{
        "framework": "MITRE ATT&CK",
        "tactic": {"id": tactic_id, "name": tactic_name,
                   "reference": f"https://attack.mitre.org/tactics/{tactic_id}/"},
        "technique": [{"id": technique_id, "name": technique_name,
                       "reference": f"https://attack.mitre.org/techniques/{technique_id}/"}],
    }]


new_endpoint_rules = 0
for action, title, severity, risk, tactic, technique in (
    ("suspicious_process", "Suspicious process simulation", "high", 65,
     ("TA0002", "Execution"), ("T1059", "Command and Scripting Interpreter")),
    ("blocked_file", "Blocked file simulation", "medium", 40,
     ("TA0002", "Execution"), ("T1204", "User Execution")),
    ("ransomware_simulation", "Ransomware prevention simulation", "critical", 88,
     ("TA0040", "Impact"), ("T1486", "Data Encrypted for Impact")),
    ("unusual_network", "Unusual network simulation", "low", 18,
     ("TA0011", "Command and Control"), ("T1071", "Application Layer Protocol")),
):
    rule_id = f"codeforge-demo-defend-{action.replace('_', '-')}"
    try:
        api(f"/api/detection_engine/rules?rule_id={rule_id}")
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        api("/api/detection_engine/rules", {
            "rule_id": rule_id, "name": f"MyScoutee demo | {title}",
            "description": "Synthetic endpoint-shaped lab signal; no host is protected or monitored by Elastic Defend.",
            "type": "query", "language": "kuery",
            "query": f'demo: true and event.action: "{action}"',
            "index": ["demo-myscoutee-endpoint"],
            "severity": severity, "risk_score": risk,
            "threat": mitre(*tactic, *technique),
            "tags": ["MyScoutee demo", "synthetic endpoint fixture"],
            "interval": "1m", "from": "now-15m", "enabled": True,
        })
        new_endpoint_rules += 1

# On a fresh lab, return from the launcher only after the managed EDR dashboard
# has all 32 synthetic alerts to display. Do not block reruns if a user has
# subsequently closed or disabled the demo alerts.
if new_endpoint_rules:
    for _ in range(60):
        result = api("/api/detection_engine/signals/search", {
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"event.module": "endpoint"}},
                {"prefix": {"host.name": "demo-"}},
                {"term": {"kibana.alert.workflow_status": "open"}},
            ]}},
        })
        if result.get("hits", {}).get("total", {}).get("value", 0) >= 32:
            break
        time.sleep(2)
    else:
        raise SystemExit("Synthetic endpoint alerts did not become available")

print(f"Kibana ready: {len(VIEWS)} data views ({created} new), "
      f"{len(dashboard_definitions)} dashboards and "
      f"{sum(len(d['panels']) for d in dashboard_definitions.values())} library visualizations, "
      "3 Discover sessions, 1 map and 5 detection rules", flush=True)
