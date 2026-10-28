#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
credential_file="$repo_root/.local/fleet.env"
mkdir -p "$repo_root/.local"
if [[ ! -f "$credential_file" ]]; then
  umask 077
  python3 - "$credential_file" <<'PY'
import secrets, sys
from pathlib import Path
Path(sys.argv[1]).write_text(
    'ELASTIC_PASSWORD=' + secrets.token_urlsafe(24) + '\n' +
    'KIBANA_PASSWORD=' + secrets.token_urlsafe(24) + '\n',
    encoding='utf-8',
)
PY
fi

cd "$repo_root"
compose=(docker compose --env-file "$credential_file" -f fleet/compose.yaml -p myscoutee-fleet)
"${compose[@]}" up -d elasticsearch

python3 - "$credential_file" <<'PY'
import base64, json, sys, time, urllib.error, urllib.request
from pathlib import Path

values = dict(line.strip().split('=', 1) for line in Path(sys.argv[1]).read_text().splitlines())
auth = base64.b64encode(f"elastic:{values['ELASTIC_PASSWORD']}".encode()).decode()
request = urllib.request.Request('http://127.0.0.1:9201/_cluster/health', headers={'Authorization': f'Basic {auth}'})
for _ in range(90):
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            if json.load(response)['status'] in ('yellow', 'green'):
                break
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        pass
    time.sleep(2)
else:
    raise SystemExit('Fleet Elasticsearch did not become healthy')
body = json.dumps({'password': values['KIBANA_PASSWORD']}).encode()
password_request = urllib.request.Request(
    'http://127.0.0.1:9201/_security/user/kibana_system/_password',
    data=body,
    method='POST',
    headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'},
)
with urllib.request.urlopen(password_request, timeout=10):
    pass
PY

"${compose[@]}" up -d kibana
python3 - <<'PY'
import time, urllib.error, urllib.request
for _ in range(120):
    try:
        with urllib.request.urlopen('http://127.0.0.1:5602/api/status', timeout=3) as response:
            if response.status == 200:
                break
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        pass
    time.sleep(2)
else:
    raise SystemExit('Fleet Kibana did not become ready')
PY
python3 fleet/bootstrap.py "$credential_file"
"${compose[@]}" up -d fleet-server
python3 - <<'PY'
import json, time, urllib.error, urllib.request
for _ in range(120):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8220/api/status', timeout=3) as response:
            if response.status == 200:
                break
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        pass
    time.sleep(2)
else:
    raise SystemExit('Fleet Server did not become reachable')
PY
"${compose[@]}" up -d fleet-agent
python3 - "$credential_file" <<'PY'
import base64, json, sys, time, urllib.error, urllib.request
from pathlib import Path

values = dict(line.split('=', 1) for line in Path(sys.argv[1]).read_text().splitlines())
auth = base64.b64encode(f"elastic:{values['ELASTIC_PASSWORD']}".encode()).decode()
request = urllib.request.Request(
    'http://127.0.0.1:5602/api/fleet/agents',
    headers={'Authorization': f'Basic {auth}', 'kbn-xsrf': 'true'},
)
for _ in range(120):
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            agents = json.load(response).get('items', [])
        online = {agent.get('policy_id') for agent in agents if agent.get('status') == 'online'}
        if {'fleet-server-policy', 'codeforge-managed-agent'} <= online:
            break
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        pass
    time.sleep(2)
else:
    raise SystemExit('Fleet agents did not become online')
PY
echo "Fleet Kibana: http://localhost:5602  |  Fleet Server: http://localhost:8220"
echo "Local login: elastic  |  password: $credential_file (ELASTIC_PASSWORD)"
