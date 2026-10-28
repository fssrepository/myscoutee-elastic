"""Local code exploration API and static UI."""

from __future__ import annotations

import json
import os
import base64
import hmac
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import es
from .scanner import scan

SOURCE = Path(os.environ.get("SOURCE_PATH", "/source"))
PROJECT = os.environ.get("PROJECT_NAME", "MyScoutee sample")
STATIC = Path(__file__).parent / "static"
ACTIVITY_FILE = Path(os.environ.get("ACTIVITY_FILE", "/activity/codeforge.jsonl"))
LOCK = threading.Lock()
STATE = {"files": 0, "findings": 0, "source": str(SOURCE), "project": PROJECT, "ready": False}


def record_activity(event_type, **details):
    event = {"occurred_at": datetime.now(timezone.utc).isoformat(),
             "event_type": event_type, "project": PROJECT, **details}
    try:
        ACTIVITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ACTIVITY_FILE.open("a", encoding="utf-8") as output:
            output.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as error:
        print(f"Activity log unavailable: {error}", flush=True)


def run_scan():
    files, findings = scan(SOURCE, PROJECT)
    previous = es.saved_statuses()
    for identifier, finding in findings:
        finding["status"] = previous.get(identifier, "open")
    es.initialize()
    es.bulk(es.FILES, files)
    es.bulk(es.FINDINGS, findings)
    STATE.update(files=len(files), findings=len(findings), ready=True, error=None)
    record_activity("scan_completed", files=len(files), findings=len(findings))
    return STATE.copy()


def facet_query(field, size=20):
    return {"terms": {"field": field, "size": size}}


def filters(params):
    clauses = []
    for field in ("module", "language", "rule", "severity", "status"):
        value = params.get(field, [""])[0]
        if value:
            clauses.append({"term": {field: value}})
    return clauses


def findings_query(params):
    query_text = params.get("q", [""])[0].strip()[:200]
    page = max(0, min(int(params.get("page", ["0"])[0]), 100))
    clauses = filters(params)
    if query_text:
        clauses.append({"multi_match": {"query": query_text,
                                         "fields": ["message^3", "excerpt^2", "path.search^2"],
                                         "type": "best_fields", "fuzziness": "AUTO"}})
    body = {
        "from": page * 20, "size": 20, "track_total_hits": True,
        "query": {"bool": {"must": clauses}} if clauses else {"match_all": {}},
        "sort": ([{"_score": "desc"}, {"path": "asc"}, {"line": "asc"}]
                 if query_text else [{"indexed_at": "desc"}, {"path": "asc"}, {"line": "asc"}]),
        "aggs": {"modules": facet_query("module"), "rules": facet_query("rule"),
                 "severity": facet_query("severity"), "status": facet_query("status"),
                 "languages": facet_query("language")},
    }
    if query_text:
        body["highlight"] = {"fields": {"excerpt": {}, "message": {}},
                             "pre_tags": ["<mark>"], "post_tags": ["</mark>"]}
    return body


def summary():
    file_result = es.search(es.FILES, {"size": 0, "aggs": {
        "modules": facet_query("module"), "languages": facet_query("language"),
        "lines": {"sum": {"field": "line_count"}},
        "largest": {"terms": {"field": "path", "size": 5, "order": {"max_lines": "desc"}},
                    "aggs": {"max_lines": {"max": {"field": "line_count"}}}},
    }})
    issue_result = es.search(es.FINDINGS, {"size": 0, "aggs": {
        "rules": facet_query("rule"), "severity": facet_query("severity"),
        "status": facet_query("status"),
        "modules": facet_query("module"),
    }})
    return {"files": file_result["hits"]["total"]["value"],
            "findings": issue_result["hits"]["total"]["value"],
            "lines": int(file_result["aggregations"]["lines"]["value"]),
            "modules": file_result["aggregations"]["modules"]["buckets"],
            "languages": file_result["aggregations"]["languages"]["buckets"],
            "largest": file_result["aggregations"]["largest"]["buckets"],
            "rules": issue_result["aggregations"]["rules"]["buckets"],
            "severity": issue_result["aggregations"]["severity"]["buckets"],
            "status": issue_result["aggregations"]["status"]["buckets"],
            "issue_modules": issue_result["aggregations"]["modules"]["buckets"],
            "project": PROJECT}


def stack_summary():
    streams = {
        "code": ("CodeForge → Elasticsearch", "forge-files,forge-findings"),
        "activity": ("Filebeat → Logstash → Elasticsearch", "forge-activity"),
        "metrics": ("Metricbeat → Elasticsearch", "metricbeat-*"),
        "uptime": ("Heartbeat → Elasticsearch", "heartbeat-*"),
        "agent": ("Elastic Agent → Elasticsearch", "metrics-system.*"),
        "audit": ("Auditbeat → Elasticsearch", "auditbeat-*"),
        "network": ("Packetbeat → Elasticsearch", "packetbeat-*"),
    }
    return {key: {"label": label, "indices": indices, "documents": es.count(indices)}
            for key, (label, indices) in streams.items()}


QUERIES = {
    "hotspots": "FROM forge-findings | STATS findings = COUNT(*) BY module | SORT findings DESC | LIMIT 20",
    "rules": "FROM forge-findings | STATS findings = COUNT(*) BY rule, severity | SORT findings DESC | LIMIT 20",
    "languages": "FROM forge-files | STATS files = COUNT(*), lines = SUM(line_count), findings = SUM(finding_count) BY language | SORT lines DESC",
    "decisions": "FROM forge-findings | STATS findings = COUNT(*) BY status, rule | SORT findings DESC | LIMIT 20",
}


class Handler(BaseHTTPRequestHandler):
    def authorized(self):
        password = os.environ.get("CODEFORGE_PASSWORD", "")
        supplied = self.headers.get("Authorization", "")
        expected = "Basic " + base64.b64encode(f"codeforge:{password}".encode()).decode()
        if password and hmac.compare_digest(supplied, expected):
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="CodeForge"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.authorized():
            return
        route = urllib.parse.urlsplit(self.path)
        params = urllib.parse.parse_qs(route.query)
        try:
            if route.path == "/api/health":
                return self.send_json(200 if STATE["ready"] else 503, STATE)
            if route.path == "/api/summary":
                return self.send_json(200, summary())
            if route.path == "/api/stack":
                return self.send_json(200, stack_summary())
            if route.path == "/api/findings":
                result = es.search(es.FINDINGS, findings_query(params))
                return self.send_json(200, {"total": result["hits"]["total"]["value"],
                    "items": [{"id": hit["_id"], **hit["_source"],
                               "highlight": hit.get("highlight", {})} for hit in result["hits"]["hits"]],
                    "facets": {name: value["buckets"] for name, value in result["aggregations"].items()}})
            if route.path == "/api/files":
                query = params.get("q", [""])[0].strip()[:200]
                clauses = filters(params)
                if query:
                    clauses.append({"multi_match": {"query": query,
                        "fields": ["content", "path.search^3"], "fuzziness": "AUTO"}})
                body = {"size": 30, "track_total_hits": True,
                    "_source": ["path", "module", "language", "line_count", "finding_count"],
                    "query": {"bool": {"must": clauses}} if clauses else {"match_all": {}},
                    "sort": [{"_score": "desc"}, {"path": "asc"}] if query else [{"finding_count": "desc"}, {"path": "asc"}]}
                if query:
                    body["highlight"] = {"fields": {"content": {"fragment_size": 160,
                                                            "number_of_fragments": 2}},
                                         "pre_tags": ["<mark>"], "post_tags": ["</mark>"]}
                result = es.search(es.FILES, body)
                return self.send_json(200, {"total": result["hits"]["total"]["value"],
                    "items": [{"id": hit["_id"], **hit["_source"],
                               "highlight": hit.get("highlight", {})} for hit in result["hits"]["hits"]]})
            if route.path.startswith("/api/files/"):
                file_id = route.path.rsplit("/", 1)[1]
                if len(file_id) != 24 or any(char not in "0123456789abcdef" for char in file_id):
                    return self.send_json(400, {"error": "Érvénytelen fájlazonosító."})
                file_result = es.get_file(file_id)
                if not file_result.get("found"):
                    return self.send_json(404, {"error": "A fájl nem található."})
                related = es.search(es.FINDINGS, {"size": 100,
                    "query": {"term": {"file_id": file_id}}, "sort": [{"line": "asc"}]})
                return self.send_json(200, {"file": file_result["_source"],
                    "findings": [hit["_source"] for hit in related["hits"]["hits"]]})
            if route.path == "/api/esql":
                name = params.get("view", ["hotspots"])[0]
                if name not in QUERIES:
                    return self.send_json(400, {"error": "Ismeretlen lekérdezés."})
                result = es.esql(QUERIES[name])
                return self.send_json(200, {"query": QUERIES[name],
                    "columns": result["columns"], "values": result["values"]})
            if route.path in ("/", "/index.html", "/style.css", "/app.js"):
                filename = "index.html" if route.path == "/" else route.path[1:]
                body = (STATIC / filename).read_bytes()
                media = {"index.html": "text/html", "style.css": "text/css",
                         "app.js": "application/javascript"}[filename]
                self.send_response(200)
                self.send_header("Content-Type", media + "; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            self.send_json(404, {"error": "Nincs ilyen útvonal."})
        except (ValueError, RuntimeError, OSError) as error:
            status = 404 if "Elasticsearch 404" in str(error) else (503 if not STATE["ready"] else 500)
            self.send_json(status, {"error": str(error)})

    def do_POST(self):
        if not self.authorized():
            return
        if self.path.startswith("/api/findings/") and self.path.endswith("/status"):
            finding_id = self.path.split("/")[3]
            if len(finding_id) != 24 or any(char not in "0123456789abcdef" for char in finding_id):
                return self.send_json(400, {"error": "Érvénytelen találatazonosító."})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 512:
                    return self.send_json(400, {"error": "Érvénytelen kérésméret."})
                try:
                    status = json.loads(self.rfile.read(size)).get("status")
                except (ValueError, AttributeError):
                    return self.send_json(400, {"error": "Érvénytelen JSON kérés."})
                if status not in ("open", "accepted", "resolved"):
                    return self.send_json(400, {"error": "Érvénytelen állapot."})
                if not LOCK.acquire(blocking=False):
                    return self.send_json(409, {"error": "Szkennelés közben nem módosítható."})
                try:
                    result = es.set_status(finding_id, status)
                    record_activity("finding_reviewed", finding_id=finding_id, status=status)
                    return self.send_json(200, {"status": status, "result": result["result"]})
                finally:
                    LOCK.release()
            except (ValueError, RuntimeError, OSError) as error:
                return self.send_json(404 if "Elasticsearch 404" in str(error) else 500,
                                      {"error": str(error)})
        if self.path != "/api/scan":
            return self.send_json(404, {"error": "Nincs ilyen útvonal."})
        if not LOCK.acquire(blocking=False):
            return self.send_json(409, {"error": "Már fut egy szkennelés."})
        try:
            STATE["ready"] = False
            return self.send_json(200, run_scan())
        except (ValueError, RuntimeError, OSError) as error:
            STATE.update(ready=False, error=str(error))
            return self.send_json(500, {"error": str(error)})
        finally:
            LOCK.release()


def main():
    for attempt in range(30):
        try:
            with LOCK:
                run_scan()
            break
        except (RuntimeError, OSError, ValueError) as error:
            STATE["error"] = str(error)
            print(f"Scan attempt {attempt + 1}: {error}", flush=True)
            time.sleep(3)
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    print(f"CodeForge serving on :8080; indexed {STATE['files']} files", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
