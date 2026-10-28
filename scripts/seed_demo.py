#!/usr/bin/env python3
"""Seed bounded, clearly fictional MyScoutee product scenarios into Elasticsearch."""

import base64
import datetime as dt
import json
import os
import urllib.error
import urllib.request


BASE = os.environ.get("ELASTIC_URL", "http://elasticsearch:9200").rstrip("/")
AUTH = base64.b64encode(
    f"{os.environ.get('ELASTIC_USERNAME', 'elastic')}:{os.environ['ELASTIC_PASSWORD']}".encode()
).decode()
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def api(path, body=None, method=None, ndjson=False):
    data = None
    if body is not None:
        data = body.encode() if ndjson else json.dumps(body).encode()
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method=method or ("POST" if body is not None else "GET"),
        headers={"Authorization": "Basic " + AUTH,
                 "Content-Type": "application/x-ndjson" if ndjson else "application/json"},
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.load(response)


def timestamp(minutes_ago):
    return (NOW - dt.timedelta(minutes=minutes_ago)).isoformat()


INDEXES = {
    "demo-myscoutee-offerings": {
        "properties": {
            "@timestamp": {"type": "date"}, "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "description": {"type": "text"}, "category": {"type": "keyword"},
            "status": {"type": "keyword"}, "language": {"type": "keyword"},
            "city": {"type": "keyword"}, "location": {"type": "geo_point"},
            "price_eur": {"type": "float"}, "rating": {"type": "float"},
            "demo": {"type": "boolean"}, "source": {"type": "keyword"},
        }
    },
    "demo-myscoutee-events": {
        "properties": {
            "@timestamp": {"type": "date"}, "event": {"properties": {
                "dataset": {"type": "keyword"}, "action": {"type": "keyword"},
                "outcome": {"type": "keyword"}}},
            "service": {"properties": {"name": {"type": "keyword"}}},
            "message": {"type": "text"}, "status": {"type": "keyword"},
            "attempts": {"type": "integer"}, "latency_ms": {"type": "integer"},
            "demo": {"type": "boolean"}, "source": {"type": "keyword"},
        }
    },
    "demo-myscoutee-endpoint": {
        "properties": {
            "@timestamp": {"type": "date"},
            "event": {"properties": {
                "action": {"type": "keyword"}, "dataset": {"type": "keyword"},
                "kind": {"type": "keyword"}, "module": {"type": "keyword"},
            }},
            "agent": {"properties": {
                "id": {"type": "keyword"}, "type": {"type": "keyword"},
            }},
            "host": {"properties": {
                "name": {"type": "keyword"},
                "os": {"properties": {"type": {"type": "keyword"}}},
            }},
            "user": {"properties": {"name": {"type": "keyword"}}},
            "message": {"type": "text"}, "demo": {"type": "boolean"},
            "source": {"type": "keyword"},
        }
    },
}


def create_index(name, mapping):
    try:
        api("/" + name, {"mappings": mapping}, method="PUT")
    except urllib.error.HTTPError as error:
        response = error.read()
        if error.code != 400 or b"resource_already_exists_exception" not in response:
            raise RuntimeError(f"Cannot create {name}: {response.decode()}") from error


for name, mapping in INDEXES.items():
    create_index(name, mapping)
api("/demo-myscoutee-events/_alias/logs-myscoutee.demo-default", {}, method="PUT")

# Real city coordinates, entirely fictional offerings. The product currently stores
# location on profiles rather than on a searchable offering document.
CITIES = (
    ("Bratislava", 17.1077, 48.1486), ("Košice", 21.2611, 48.7164),
    ("Prague", 14.4378, 50.0755), ("Brno", 16.6068, 49.1951),
    ("Vienna", 16.3738, 48.2082), ("Budapest", 19.0402, 47.4979),
    ("Trnava", 17.5875, 48.3774), ("Nitra", 18.0864, 48.3061),
)
SERVICES = (
    ("maintenance", "Home repair visit"), ("plumbing", "Plumbing inspection"),
    ("electrical", "Electrical safety check"), ("cleaning", "Apartment cleaning"),
    ("renovation", "Room renovation consult"), ("fitness", "Personal fitness session"),
    ("education", "Math tutoring"), ("other", "Neighbourhood assistance"),
)
docs = []
for city_i, (city, lon, lat) in enumerate(CITIES):
    for service_i, (category, title) in enumerate(SERVICES):
        number = city_i * len(SERVICES) + service_i
        docs.append(("demo-myscoutee-offerings", f"offering-{number:03d}", {
            "@timestamp": timestamp(25 + number * 37),
            "title": f"{title} in {city}",
            "description": f"Fictional {category} service listing for a MyScoutee search and map demo.",
            "category": category,
            "status": "published" if number % 7 else "draft",
            "language": "sk" if city_i in (0, 1, 6, 7) else "cs" if city_i in (2, 3) else "de" if city_i == 4 else "hu",
            "city": city,
            "location": {"lon": lon + (service_i - 3.5) * 0.012,
                         "lat": lat + (service_i - 3.5) * 0.008},
            "price_eur": 15 + service_i * 8 + city_i * 2,
            "rating": round(3.7 + (number % 12) * 0.1, 1),
            "demo": True, "source": "synthetic fixture",
        }))

for number in range(96):
    failed = number % 13 == 0
    action = "ticket.checkin.replay" if number % 4 == 0 else "notification.deliver"
    dataset = "myscoutee.ticket_audit" if action.startswith("ticket") else "myscoutee.outbox"
    outcome = "failure" if failed else "success"
    docs.append(("demo-myscoutee-events", f"event-{number:03d}", {
        "@timestamp": timestamp(8 + number * 12),
        "event": {"dataset": dataset, "action": action, "outcome": outcome},
        "service": {"name": "myscoutee-ticket" if action.startswith("ticket") else "myscoutee-notification"},
        "message": ("Synthetic replay blocked for an already used ticket" if failed and action.startswith("ticket")
                    else "Synthetic delivery retry queued" if failed
                    else "Synthetic event processed successfully"),
        "status": "retry" if failed else "completed",
        "attempts": 2 if failed else 1,
        "latency_ms": 55 + (number * 23) % 520,
        "demo": True, "source": "synthetic fixture",
    }))

# These are synthetic Elastic Defend-shaped signals. Detection rules, rather than
# direct writes to a system alert index, turn them into local Security alerts.
# The demo marker and demo-* hostnames distinguish them from protected endpoints.
HOSTS = (
    ("demo-web-01", "linux", "demo.alex"),
    ("demo-worker-02", "linux", "demo.sara"),
    ("demo-editor-03", "windows", "demo.morgan"),
    ("demo-client-04", "macos", "demo.taylor"),
)
SCENARIOS = (
    ("suspicious_process", "Synthetic Detection: unusual scripting process on a demo host"),
    ("blocked_file", "Synthetic Prevention: suspicious file write blocked on a demo host"),
    ("ransomware_simulation", "Synthetic Ransomware Prevention: simulated file encryption blocked"),
    ("unusual_network", "Synthetic Detection: unusual network connection on a demo host"),
)
for scenario_i, (action, message) in enumerate(SCENARIOS):
    for sample_i in range(8):
        number = scenario_i * 8 + sample_i
        host_name, os_type, user_name = HOSTS[(sample_i + scenario_i) % len(HOSTS)]
        # Daily IDs make a restart on a later date produce fresh demo alerts.
        # Repeated starts on the same day update the same 32 source records.
        docs.append(("demo-myscoutee-endpoint", f"endpoint-{NOW:%Y%m%d}-{number:03d}", {
            "@timestamp": timestamp(2 + number % 9),
            "event": {"action": action, "dataset": "endpoint.alerts",
                      "kind": "event", "module": "endpoint"},
            "agent": {"id": f"demo-agent-{(sample_i + scenario_i) % len(HOSTS) + 1:02d}",
                      "type": "endpoint"},
            "host": {"name": host_name, "os": {"type": os_type}},
            "user": {"name": user_name},
            "message": message,
            "demo": True, "source": "synthetic Elastic Defend-style fixture",
        }))

lines = []
for index, identifier, document in docs:
    lines.append(json.dumps({"index": {"_index": index, "_id": identifier}}))
    lines.append(json.dumps(document))
result = api("/_bulk?refresh=wait_for", "\n".join(lines) + "\n", ndjson=True)
if result.get("errors"):
    failures = [item for item in result["items"] if item["index"].get("error")]
    raise RuntimeError(f"Demo seed failed for {len(failures)} documents: {failures[:2]}")
print("Seeded 64 fictional offerings, 96 synthetic service events "
      "and 32 synthetic endpoint signals", flush=True)
