#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
credential_file="$repo_root/.local/core.env"
mkdir -p "$repo_root/.local"
if [[ ! -f "$credential_file" ]]; then
  umask 077
  python3 - "$credential_file" <<'PY'
import secrets, sys
from pathlib import Path
Path(sys.argv[1]).write_text(
    'ELASTIC_PASSWORD=' + secrets.token_urlsafe(24) + '\n' +
    'KIBANA_PASSWORD=' + secrets.token_urlsafe(24) + '\n' +
    'CODEFORGE_PASSWORD=' + secrets.token_urlsafe(24) + '\n', encoding='utf-8')
PY
fi
chmod 600 "$credential_file"
python3 - "$credential_file" <<'PY'
import secrets, sys
from pathlib import Path

path = Path(sys.argv[1])
lines = path.read_text(encoding='utf-8').splitlines()
values = dict(line.split('=', 1) for line in lines if '=' in line)
names = ('KIBANA_SAVED_OBJECTS_KEY', 'KIBANA_SECURITY_KEY', 'KIBANA_REPORTING_KEY')
with path.open('a', encoding='utf-8') as output:
    for name in names:
        if name not in values:
            values[name] = secrets.token_urlsafe(48)
            output.write(f'{name}={values[name]}\n')
for name in names:
    if len(values[name]) < 32:
        raise SystemExit(f'{name} must be at least 32 characters')
PY
cd "$repo_root"
compose=(docker compose --env-file "$credential_file" -p myscoutee-elastic)
"${compose[@]}" up -d elasticsearch

python3 - "$credential_file" <<'PY'
import base64, json, sys, time, urllib.error, urllib.request
from pathlib import Path

values = dict(line.split('=', 1) for line in Path(sys.argv[1]).read_text().splitlines())
auth = base64.b64encode(f"elastic:{values['ELASTIC_PASSWORD']}".encode()).decode()
request = urllib.request.Request('http://127.0.0.1:9200/_cluster/health',
                                 headers={'Authorization': f'Basic {auth}'})
for _ in range(90):
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            if json.load(response)['status'] in ('yellow', 'green'):
                break
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        pass
    time.sleep(2)
else:
    raise SystemExit('Core Elasticsearch did not become healthy with saved credentials')
body = json.dumps({'password': values['KIBANA_PASSWORD']}).encode()
password_request = urllib.request.Request(
    'http://127.0.0.1:9200/_security/user/kibana_system/_password', data=body,
    method='POST', headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'})
with urllib.request.urlopen(password_request, timeout=10):
    pass
PY

"${compose[@]}" up --build -d
"${compose[@]}" run --rm --no-deps demo-bootstrap
"${compose[@]}" run --rm --no-deps kibana-bootstrap
echo "CodeForge: http://localhost:8088  |  Kibana: http://localhost:5601"
echo "Kibana/Elasticsearch login: elastic (ELASTIC_PASSWORD in .local/core.env)"
echo "CodeForge login: codeforge (CODEFORGE_PASSWORD in .local/core.env)"
