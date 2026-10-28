# CodeForge · Elastic Stack lab

CodeForge is a Dockerized, SonarQube-inspired workspace for exploring source code with Elasticsearch and Kibana. It scans Java and TypeScript files, records simple review findings, and makes the results searchable. The bundled four-file sample is fictional; it does not copy MyScoutee source code. Mount the sibling MyScoutee backend to analyze the real checkout.

## Start the core lab

Allow at least 6 GB of Docker memory and approximately 10 GB of free disk space. Published ports bind to localhost. Run from this repository root:

~~~sh
bash scripts/core-lab.sh
~~~

To scan the real sibling checkout:

~~~sh
SOURCE_ROOT=../myscoutee-backend PROJECT_NAME=MyScoutee bash scripts/core-lab.sh
~~~

The launcher preserves existing Docker data volumes. On first run it creates random passwords and three persistent Kibana encryption keys in Git-ignored `.local/core.env` with owner-only permissions. Repeated runs reuse these values. Keep the file: deleting it can make previously encrypted Kibana objects unreadable.

### Addresses and usernames

| Surface | Address | Username | Password location |
| --- | --- | --- | --- |
| CodeForge | http://localhost:8088 | `codeforge` | `.local/core.env` → `CODEFORGE_PASSWORD` |
| Core Kibana / Discover | http://localhost:5601/app/discover | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Findings dashboard and heatmap | http://localhost:5601/app/dashboards#/view/codeforge-findings-overview | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Stack telemetry dashboard | http://localhost:5601/app/dashboards#/view/codeforge-stack-telemetry | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Service discovery demo | http://localhost:5601/app/dashboards#/view/codeforge-demo-offerings | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Event reliability demo | http://localhost:5601/app/dashboards#/view/codeforge-demo-reliability | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Saved offering map | http://localhost:5601/app/maps/map/codeforge-demo-offerings-map | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Published offerings in Discover | http://localhost:5601/app/discover#/view/codeforge-demo-published-offerings | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Retry events in Discover | http://localhost:5601/app/discover#/view/codeforge-demo-retry-events | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Synthetic endpoint signals in Discover | http://localhost:5601/app/discover#/view/codeforge-demo-endpoint-signals | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Visualize Library | http://localhost:5601/app/visualize | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Security detection rules | http://localhost:5601/app/security/rules | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Security rule monitoring (managed dashboard) | http://localhost:5601/app/dashboards#/view/security-detection-rule-monitoring-default | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Elastic Defend managed dashboard (demo alerts) | http://localhost:5601/app/dashboards#/view/endpoint-475a47e9-2cd7-4f5f-a2bf-efced65e9a85 | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Core Elasticsearch API | http://localhost:9200 | `elastic` | `.local/core.env` → `ELASTIC_PASSWORD` |
| Fleet Kibana / Agents | http://localhost:5602/app/fleet/agents | `elastic` | `.local/fleet.env` → `ELASTIC_PASSWORD` |
| Fleet System metrics dashboard | http://localhost:5602/app/dashboards#/view/codeforge-fleet-system | `elastic` | `.local/fleet.env` → `ELASTIC_PASSWORD` |
| Fleet Visualize Library | http://localhost:5602/app/visualize | `elastic` | `.local/fleet.env` → `ELASTIC_PASSWORD` |
| Fleet Elasticsearch API | http://localhost:9201 | `elastic` | `.local/fleet.env` → `ELASTIC_PASSWORD` |

The `KIBANA_PASSWORD` in each file belongs to Kibana's internal `kibana_system` account. For the browser login, use the `ELASTIC_PASSWORD` from the matching lab. The core and Fleet labs have different passwords.

Core Kibana opens Discover. The launcher seeds 64 fictional offerings, 96 synthetic service events and 32 synthetic endpoint signals, then creates eleven data views, four custom dashboards, 24 library visualizations, three saved Discover sessions, one map, and five Security detection rules. It waits for a demo endpoint alert on a fresh installation. These fixtures and setup steps are versioned in this repository and run on startup without manual Kibana editing. Find the dashboards under **Analytics → Dashboards**:

- **CodeForge | Findings overview:** file and finding counts, severity pie chart, module × rule heatmap, module ranking, and review status. Its default time range is 30 days.
- **CodeForge | Stack telemetry:** activity events, HTTP checks, metric samples, time series, and source breakdowns. Its default time range is 24 hours.
- **MyScoutee demo | Service discovery:** fictional listings by category, city, status and language, with average price. Open the saved **MyScoutee demo | Service offering map** in **Analytics → Maps** to inspect example city locations. The **Maps → Create** screen is an empty editor by design; open the saved map from the Maps list.
- **MyScoutee demo | Event reliability:** synthetic notification outbox and ticket check-in events, outcomes and latency.

Open **Analytics → Visualize library** for the reusable charts behind all four custom dashboards. Open **Analytics → Discover → Open** for **MyScoutee demo | Published offerings**, **MyScoutee demo | Retries and replay failures**, or **MyScoutee demo | Endpoint signals**. The saved map and Discover sessions use a 30-day window; the event dashboard uses 24 hours. If a chart appears empty after changing its time picker, restore that window.

The fixture is entirely fictional. It uses real city coordinates but invents listings, prices, ratings and events. Its service categories and event scenarios follow the MyScoutee backend's existing concepts; it is not an integration with live MyScoutee data. The `demo-myscoutee-offerings` index has a real `geo_point` mapping; `demo-myscoutee-events` holds structured outcomes and is also available under the `logs-myscoutee.demo-default` alias for log exploration. Stable document IDs keep these two indices at 160 records across reruns. The endpoint fixture uses 32 IDs per UTC day so a later launch can produce fresh Security alerts. The bootstrap does not delete user data or Docker volumes.

The Security app needs a persistent encrypted saved objects key. The core launcher provisions it along with stable session and reporting keys. Under **Security → Rules**, the ticket replay rule and four endpoint simulation rules create local alerts without external notification actions. The managed **[Elastic Defend] Endpoint Detection and Response** dashboard now shows demo detection, prevention and ransomware counts; severity, MITRE technique and OS charts; and the top demo hosts and users. Select **Today** or **Last 24 hours** if its default 15-minute range has expired. A later day's `core-lab.sh` run generates that day's synthetic alerts.

The separate managed **[Elastic Security] Detection rule monitoring** dashboard reports real rule execution health. Its **Warning** and **Failed** cards may display `(null)` when their filters find no matching status-change events in the selected time range; read that as zero warnings or failures, not missing demo data. **Succeeded** should increase as the five rules run. The launcher does not create deliberately failing rules to populate the other cards. See [Elastic's rule monitoring guide](https://www.elastic.co/docs/solutions/security/detect-and-alert/monitor-rule-executions) for the status meanings.

This is an **Elastic Defend-shaped simulation**, not an installed Elastic Defend integration and not proof that any host is protected. Source events live only in `demo-myscoutee-endpoint`, carry `demo: true` and `source: synthetic Elastic Defend-style fixture`, and use `demo-*` host and user names. The rules use Kibana's detection API to produce alerts; the bootstrap never writes directly to Security's system alert index or modifies the managed dashboard. Real Elastic Defend coverage requires the integration and an Agent on a supported host. Security Discover can also query the `logs-myscoutee.demo-default` alias; other host and network views still require real telemetry.

Without `SOURCE_ROOT`, CodeForge scans `samples/myscoutee-inspired`. The scanner takes at most 350 Java files and 350 TypeScript files, up to 128 KB each. It skips generated files, dependencies, and `secrets` directories. Selection is deterministic by path. The source mount is read-only; use the button in CodeForge to rescan it.

To switch the mounted source in an existing Compose project, stop the services while preserving volumes, then start with the desired `SOURCE_ROOT`:

~~~sh
docker compose --env-file .local/core.env -p myscoutee-elastic down
SOURCE_ROOT=../myscoutee-backend PROJECT_NAME=MyScoutee bash scripts/core-lab.sh
~~~

## Stack components

| Component | Data path or role | Start |
| --- | --- | --- |
| Elasticsearch | Stores source files, findings, activity, and telemetry | Core |
| Kibana | Discover, dashboards, Dev Tools, and Security app | Core |
| Logstash | Processes Filebeat activity timestamps into `forge-activity` | Core |
| Filebeat | Ships CodeForge JSONL activity to Logstash | Core |
| Metricbeat | Collects Elasticsearch cluster, node, and index metrics | Core |
| Heartbeat | Checks CodeForge, Elasticsearch, and Kibana over HTTP | Core |
| Elastic Agent | Standalone CPU and memory metrics | `agent` profile |
| Auditbeat | Source file inventory and file changes | `deep` profile |
| Packetbeat | HTTP traffic in the CodeForge container network namespace | `deep` profile |
| Fleet | Separate secured Elasticsearch, Kibana, Fleet Server, managed Agent, and System integration | `scripts/fleet-lab.sh` |
| Winlogbeat | Windows event logs; not run in this Linux Docker lab | Separate Windows host |

Start optional core collectors after the core lab:

~~~sh
docker compose --env-file .local/core.env -p myscoutee-elastic --profile agent up -d elastic-agent
SOURCE_ROOT=../myscoutee-backend docker compose --env-file .local/core.env -p myscoutee-elastic --profile deep up -d auditbeat packetbeat
~~~

CodeForge's **Stack lab** view shows actual document counts per route. A zero count is a reason to inspect the relevant service logs. Rescanning or changing a finding status creates a new `forge-activity` event. To generate Packetbeat traffic, open CodeForge pages or call its API. Auditbeat inventories the source on first start and records subsequent changes to the mounted source.

### Fleet lab

Fleet runs as a separate Compose project with its own Elasticsearch data and agent volumes. Start it with:

~~~sh
bash scripts/fleet-lab.sh
~~~

**Fleet Kibana username: `elastic`.** Its password is the `ELASTIC_PASSWORD` value in `.local/fleet.env`, not the value in `.local/core.env`. The Fleet Server status endpoint is http://localhost:8220/api/status. The launcher waits for Fleet Server and the managed Agent to come online, creates a Discover data view for `metrics-system.*`, and installs the Fleet System metrics dashboard with CPU, memory, and dataset charts. Its six reusable charts also appear in that Kibana's **Visualize library**.

~~~sh
docker compose --env-file .local/fleet.env -f fleet/compose.yaml -p myscoutee-fleet ps -a
~~~

## What to try

- Search source content and findings with relevance ranking, typo tolerance, and highlighted excerpts.
- Filter findings by module, language, rule, severity, and review status; compare aggregations and hotspots in Kibana.
- Mark findings `open`, `accepted`, or `resolved`. The decision is stored as an Elasticsearch document update and survives a rescan of the same finding.
- Inspect the `forge-ingest` pipeline, which stamps `indexed_at` on indexed source and finding records.
- Run the four prepared ES|QL queries in CodeForge's Stack lab and adapt them in Kibana Dev Tools.
- Explore the prepared `forge-files`, `forge-findings`, `forge-activity`, `metricbeat-*`, and `heartbeat-*` data views. Optional collectors add `metrics-system.*`, `auditbeat-*`, and `packetbeat-*`.

Try `Notification`, `event`, `repository`, or a real source filename. The four findings are work markers, lines over 160 characters, files over 500 lines, and Java catches of `Exception` or `Throwable`. These are heuristics, not verified defects. Full source text is stored in the local Elasticsearch volume, so mount confidential repositories only on a trusted machine.

CodeForge API examples; `curl` prompts for the `codeforge` password:

~~~sh
curl -u codeforge http://localhost:8088/api/summary
curl -u codeforge 'http://localhost:8088/api/findings?rule=work_marker'
curl -u codeforge 'http://localhost:8088/api/esql?view=hotspots'
curl -u codeforge http://localhost:8088/api/stack
~~~

## Security and local data

Elasticsearch and Kibana security is enabled in both labs. CodeForge protects its UI and API with HTTP Basic authentication. The core collectors authenticate when writing to Elasticsearch; Fleet uses its own credentials and agent keys. Internal container traffic remains plain HTTP, and published ports bind to `127.0.0.1`. This setup is for local evaluation.

To remove all **core** indices and volumes, run the destructive command below only when you intend to discard that data:

~~~sh
docker compose --env-file .local/core.env -p myscoutee-elastic down -v
~~~

## Development checks

~~~sh
python3 -m unittest discover -s tests -v
docker compose --env-file .local/core.env -p myscoutee-elastic config --quiet
docker compose --env-file .local/fleet.env -f fleet/compose.yaml -p myscoutee-fleet config --quiet
~~~

All Elastic containers use pinned version `9.5.5`. Configuration references: [Elasticsearch on Docker](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/install-elasticsearch-docker-basic), [Logstash on Docker](https://www.elastic.co/docs/reference/logstash/docker-config), [Elastic Agent containers](https://www.elastic.co/docs/reference/fleet/elastic-agent-container), and the [ES|QL REST API](https://www.elastic.co/docs/reference/query-languages/esql/esql-rest).

The English, MyScoutee-branded [Elastic Stack lab and integration guide](guides/MyScoutee_Elastic_Stack_Lab_EN.pdf) covers the working data paths, three concrete MyScoutee use cases, possible replacements, and integration decision points. Its editable source is `guides/build_elastic_guide.py`.
