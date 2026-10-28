"""Elasticsearch REST calls and the lab's index contract."""

from __future__ import annotations

import json
import os
import base64
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("ELASTIC_URL", "http://localhost:9200").rstrip("/")
FILES = "forge-files"
FINDINGS = "forge-findings"
PIPELINE = "forge-ingest"


def request(method: str, path: str, body=None, content_type="application/json"):
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
    headers = {"Content-Type": content_type}
    if os.environ.get("ELASTIC_PASSWORD"):
        credentials = f"{os.environ.get('ELASTIC_USERNAME', 'elastic')}:{os.environ['ELASTIC_PASSWORD']}"
        headers["Authorization"] = "Basic " + base64.b64encode(credentials.encode()).decode()
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            payload = response.read()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:600]
        raise RuntimeError(f"Elasticsearch {error.code}: {detail}") from error


def initialize():
    request("PUT", f"/_ingest/pipeline/{PIPELINE}", {
        "description": "Stamp indexed source and finding records",
        "processors": [{"set": {"field": "indexed_at", "value": "{{{_ingest.timestamp}}}"}}],
    })
    for name, properties in (
        (FILES, {
            "project": {"type": "keyword"}, "path": {"type": "keyword", "fields": {"search": {"type": "text"}}},
            "module": {"type": "keyword"}, "language": {"type": "keyword"},
            "line_count": {"type": "integer"}, "finding_count": {"type": "integer"},
            "content": {"type": "text"}, "indexed_at": {"type": "date"},
        }),
        (FINDINGS, {
            "project": {"type": "keyword"}, "file_id": {"type": "keyword"},
            "path": {"type": "keyword", "fields": {"search": {"type": "text"}}}, "module": {"type": "keyword"},
            "language": {"type": "keyword"}, "rule": {"type": "keyword"},
            "severity": {"type": "keyword"}, "status": {"type": "keyword"}, "line": {"type": "integer"},
            "excerpt": {"type": "text"}, "message": {"type": "text"},
            "indexed_at": {"type": "date"},
        }),
    ):
        try:
            request("DELETE", f"/{name}")
        except RuntimeError as error:
            if "Elasticsearch 404" not in str(error):
                raise
        request("PUT", f"/{name}", {"settings": {"number_of_shards": 1, "number_of_replicas": 0},
                                   "mappings": {"dynamic": "strict", "properties": properties}})


def bulk(name: str, documents):
    for start in range(0, len(documents), 250):
        chunk = documents[start:start + 250]
        lines = []
        for identifier, document in chunk:
            lines.append(json.dumps({"index": {"_index": name, "_id": identifier}}, ensure_ascii=False))
            lines.append(json.dumps(document, ensure_ascii=False))
        body = ("\n".join(lines) + "\n").encode()
        result = request("POST", f"/_bulk?pipeline={PIPELINE}", body, "application/x-ndjson")
        if result.get("errors"):
            failures = [item["index"].get("error") for item in result["items"] if item["index"].get("error")]
            raise RuntimeError(f"Bulk index error: {failures[:2]}")
    request("POST", f"/{name}/_refresh")


def search(index, body):
    return request("POST", f"/{index}/_search", body)


def get_file(file_id):
    return request("GET", f"/{FILES}/_doc/{urllib.parse.quote(file_id, safe='')}")


def esql(query):
    return request("POST", "/_query", {"query": query})


def saved_statuses():
    try:
        result = search(FINDINGS, {"size": 10000, "_source": ["status"],
                                   "query": {"terms": {"status": ["accepted", "resolved"]}}})
    except RuntimeError as error:
        if "Elasticsearch 404" in str(error):
            return {}
        raise
    return {hit["_id"]: hit["_source"]["status"] for hit in result["hits"]["hits"]}


def set_status(finding_id, status):
    return request("POST", f"/{FINDINGS}/_update/{finding_id}?refresh=wait_for",
                   {"doc": {"status": status}})


def count(pattern):
    try:
        return request("GET", f"/{pattern}/_count")["count"]
    except RuntimeError as error:
        if "Elasticsearch 404" in str(error):
            return 0
        raise
