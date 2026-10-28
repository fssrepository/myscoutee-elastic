#!/usr/bin/env python3
"""Build the English MyScoutee Elastic lab guide with ReportLab."""
from pathlib import Path
from xml.sax.saxutils import escape
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "MyScoutee_Elastic_Stack_Lab_EN.pdf"
LOGO = ROOT / "assets/myscoutee-heart.png"
FONT = Path("/usr/share/fonts/truetype/dejavu")
for name, filename in (("Body", "DejaVuSans.ttf"), ("Bold", "DejaVuSans-Bold.ttf"), ("Mono", "DejaVuSansMono.ttf")):
    pdfmetrics.registerFont(TTFont(name, str(FONT / filename)))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Bold", italic="Body", boldItalic="Bold")

W, H = A4
M, CW = 43, W - 86
INK = colors.HexColor("#183047")
MUTED = colors.HexColor("#53697C")
BLUE = colors.HexColor("#245CC5")
TEAL = colors.HexColor("#087E80")
GOLD = colors.HexColor("#A86612")
PALE = colors.HexColor("#F0F5FA")
LINE = colors.HexColor("#D5DFE9")
WHITE = colors.white
STYLES = {
    "body": ParagraphStyle("body", fontName="Body", fontSize=9.4, leading=14, textColor=INK),
    "small": ParagraphStyle("small", fontName="Body", fontSize=8.1, leading=11.8, textColor=MUTED),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=8.2, leading=11.7, textColor=INK),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=7.7, leading=12, textColor=INK),
    "card": ParagraphStyle("card", fontName="Body", fontSize=8.7, leading=12.5, textColor=INK),
}

os.environ["SOURCE_DATE_EPOCH"] = "1793059200"  # 2026-10-27 00:00 UTC
c = canvas.Canvas(str(OUT), pagesize=A4, pageCompression=1, invariant=1)
c.setTitle("Elastic Stack Lab - MyScoutee Integration Guide")
c.setAuthor("MyScoutee")
c.setSubject("Working Docker lab and concrete MyScoutee integration choices")
c.setKeywords("MyScoutee, Elasticsearch, Kibana, Logstash, Beats, Elastic Agent, Fleet")
y = 0
n = 0
TOTAL = 8


def para(value, style="body", gap=9, indent=0):
    global y
    item = Paragraph(value, STYLES[style])
    _, height = item.wrap(CW - indent, H)
    if y - height < 54:
        raise ValueError(f"Page {n} overflow near {value[:60]}")
    item.drawOn(c, M + indent, y - height)
    y -= height + gap


def heading(value):
    global y
    y -= 5
    c.setFont("Bold", 12)
    c.setFillColor(INK)
    c.drawString(M, y, value)
    y -= 21


def page(kicker, title, subtitle):
    global y, n
    if n:
        c.showPage()
    n += 1
    if n == 1:
        c.drawImage(str(LOGO), M, H - 54, width=28, height=28, mask="auto")
    c.setFont("Bold", 8)
    c.setFillColor(TEAL)
    c.drawString(M + (37 if n == 1 else 0), H - 39, "MYSCOUTEE / LEARNING")
    c.setFont("Body", 8)
    c.setFillColor(MUTED)
    c.drawRightString(W - M, H - 39, kicker.upper())
    c.setStrokeColor(LINE)
    c.line(M, 43, W - M, 43)
    c.setFont("Body", 7.3)
    c.drawString(M, 29, "Elastic Stack lab  |  v1.2.1  |  27 October 2026")
    c.drawRightString(W - M, 29, f"{n:02d} / {TOTAL:02d}")
    c.bookmarkPage(f"page-{n}")
    c.addOutlineEntry(title.replace("<br/>", " "), f"page-{n}", level=0)
    y = H - 88
    item = Paragraph(title, ParagraphStyle("title", fontName="Bold", fontSize=25, leading=30, textColor=INK))
    _, height = item.wrap(CW, H)
    item.drawOn(c, M, y - height)
    y -= height + 11
    para(subtitle, "small", 19)


def table(rows, widths, padding=7):
    global y
    values = [[Paragraph(str(cell), STYLES["cell"]) for cell in row] for row in rows]
    t = Table(values, colWidths=[CW * x for x in widths], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
        ("LINEBELOW", (0, 0), (-1, -1), .5, LINE),
    ]))
    _, height = t.wrap(CW, H)
    if y - height < 54:
        raise ValueError(f"Table overflow on page {n}")
    t.drawOn(c, M, y - height)
    y -= height + 14


def note(label, body, accent=TEAL):
    global y
    content = Paragraph(f"<b>{label}</b> {body}", STYLES["card"])
    _, height = content.wrap(CW - 25, H)
    box_height = height + 20
    if y - box_height < 54:
        raise ValueError(f"Note overflow on page {n}")
    c.setFillColor(PALE)
    c.setStrokeColor(LINE)
    c.roundRect(M, y - box_height, CW, box_height, 7, fill=1, stroke=1)
    c.setFillColor(accent)
    c.roundRect(M, y - box_height, 4, box_height, 2, fill=1, stroke=0)
    content.drawOn(c, M + 13, y - height - 10)
    y -= box_height + 13


def code(lines):
    global y
    for line in lines:
        para(escape(line), "code", 2, 8)
    y -= 8


def flow(items, caption):
    global y
    top = y
    gap = 14
    widths = [(CW - gap * (len(items) - 1)) / len(items)] * len(items)
    x = M
    for i, (label, body) in enumerate(items):
        width = widths[i]
        c.setFillColor(PALE)
        c.setStrokeColor(LINE)
        c.roundRect(x, top - 62, width, 62, 6, fill=1, stroke=1)
        c.setFillColor(BLUE if i == 0 else TEAL)
        c.rect(x, top - 3, width, 3, fill=1, stroke=0)
        item = Paragraph(f"<b>{label}</b><br/>{body}", STYLES["card"])
        _, height = item.wrap(width - 14, 50)
        item.drawOn(c, x + 7, top - (62 + height) / 2)
        x += width + gap
        if i < len(items) - 1:
            c.setFillColor(BLUE)
            c.setFont("Bold", 11)
            c.drawCentredString(x - gap / 2, top - 35, ">")
    y -= 72
    para(caption, "small", 14)


page("01 / Overview", "Elastic Stack lab<br/>for MyScoutee",
     "A working local Docker lab and an integration decision guide. Code analysis ran against the real MyScoutee checkout; product scenarios use clearly fictional seed data.")
note("Measured baseline, 27 October 2026.", "The search index contains 700 Java/TypeScript files, 140,898 source lines and 534 heuristic findings. Filebeat-Logstash, Metricbeat and Heartbeat also wrote documents into Elasticsearch.")
heading("What does this lab build?")
flow([("Source", "MyScoutee repo<br/>read-only mount"), ("CodeForge", "scanner, API,<br/>review UI"), ("Elasticsearch", "search, aggregation,<br/>ES|QL")],
     "Figure 1. Code analysis is a separate product. The MyScoutee application sends no live user data to it.")
flow([("Activity log", "CodeForge JSONL"), ("Filebeat", "file collection"), ("Logstash", "timestamp and<br/>transformation"), ("Kibana", "Discover / Dev Tools")],
     "Figure 2. The same lab stores processed events in Elasticsearch and explores them in Kibana.")
para("<b>Goal:</b> exercise Elastic Stack search, processing and observability on real data paths. The lab also preloads fictional offerings, service events and endpoint-shaped signals so Maps, Discover, Security and charts have content on first start.")
note("Scope.", "The 534 findings come from simple heuristics, not verified defects. This guide does not imply that the MyScoutee backend already connects to Elasticsearch.", GOLD)

page("02 / Start", "Start and verify the lab",
     "Run commands from the myscoutee-elastic repository root. Localhost ports and the read-only source mount are intended for local evaluation.")
heading("Run against the real checkout")
code(["SOURCE_ROOT=../myscoutee-backend PROJECT_NAME=MyScoutee \\", "  bash scripts/core-lab.sh"])
table([
    ["<b>Surface</b>", "<b>Address</b>", "<b>Use / login</b>"],
    ["CodeForge", "localhost:8088", "Search, findings, Stack lab; codeforge login"],
    ["Kibana Discover", "localhost:5601/app/discover", "Data views and ES|QL; elastic login"],
    ["Findings dashboard", "localhost:5601/app/dashboards#/view/codeforge-findings-overview", "Heatmap, severity pie, module and review charts"],
    ["Telemetry dashboard", "localhost:5601/app/dashboards#/view/codeforge-stack-telemetry", "Activity, HTTP checks and metric samples"],
    ["Elasticsearch", "localhost:9200", "Authenticated REST API and index checks"],
    ["Fleet Kibana", "localhost:5602/app/fleet/agents", "Separate lab; elastic login"],
], [.23, .42, .35], 5)
para("Start Fleet with <b>bash scripts/fleet-lab.sh</b>. Its prepared System metrics dashboard is at <b>localhost:5602/app/dashboards#/view/codeforge-fleet-system</b>. Core passwords are in <b>.local/core.env</b>: use ELASTIC_PASSWORD for Kibana/Elasticsearch and CODEFORGE_PASSWORD for CodeForge. This file also holds persistent Kibana encryption keys. <b>Fleet Kibana username: elastic.</b> Its password is the ELASTIC_PASSWORD value in the separate <b>.local/fleet.env</b>. Both files stay outside Git.", "small", 8)
heading("Open prepared views")
code(["# Log in through the browser, then open Analytics > Dashboards", "# Select CodeForge | Findings overview or Stack telemetry"])
para("Startup prepares eleven Discover data views, four custom dashboards and 24 reusable library charts. The real CodeForge and Stack paths include <b>forge-files</b>, <b>forge-findings</b>, <b>forge-activity</b>, <b>metricbeat-*</b> and <b>heartbeat-*</b>. Rescan or change a finding review state to generate another activity event.")
para("Also open <b>Analytics &gt; Maps</b> and select <b>MyScoutee demo | Service offering map</b>; <b>Analytics &gt; Visualize library</b> contains reusable charts. Three saved Discover sessions and five synthetic rules under <b>Security &gt; Rules</b> are prepared. The empty Maps Create page is an editor, not the saved map.", "small", 6)
para("In <b>Analytics &gt; Dashboards</b>, open the managed <b>[Elastic Defend] Endpoint Detection and Response</b> dashboard. Its endpoint alerts are synthetic; choose <b>Today</b> when the 15-minute default range no longer includes them.", "small", 6)
note("Bounded scan.", "The scanner reads at most 350 files per language and 128 KB per file. Full source text remains in the local Elasticsearch volume; mount confidential repositories only on a trusted machine.")

page("03 / Components", "Data paths across the Stack",
     "Statuses combine verified local document counts on 27 October 2026 with the Compose profiles. A running container alone is not proof of a working pipeline.")
table([
    ["<b>Component</b>", "<b>Lab data / capability</b>", "<b>Status</b>"],
    ["Elasticsearch + Kibana", "Code, findings, logs, telemetry, search and visualization", "Verified"],
    ["Demo fixtures", "64 fictional offerings; 96 service events; 32 endpoint signals", "Seeded on start"],
    ["Logstash + Filebeat", "CodeForge JSONL -&gt; 5044 -&gt; forge-activity", "Verified: documents &gt; 0"],
    ["Metricbeat", "Elasticsearch cluster, node and index metrics", "Verified: documents &gt; 0"],
    ["Heartbeat", "HTTP probes for CodeForge, ES and Kibana", "Verified: documents &gt; 0"],
    ["Elastic Agent", "Standalone CPU and memory metrics", "agent profile; verified"],
    ["Auditbeat + Packetbeat", "Source file inventory and CodeForge HTTP traffic", "deep profile; verified"],
    ["Fleet + Winlogbeat", "Managed agent; Windows event logs", "Fleet verified / Windows host"],
], [.28, .49, .23], 6)
heading("Optional paths")
code(["docker compose --env-file .local/core.env --profile agent up -d elastic-agent", "SOURCE_ROOT=../myscoutee-backend \\", "  docker compose --env-file .local/core.env --profile deep up -d auditbeat packetbeat"])
code(["bash scripts/fleet-lab.sh  # separate Fleet environment"])
para("The separate authenticated Fleet lab at <b>localhost:5602</b> has a healthy Fleet Server, a managed Agent and System integration metrics. Winlogbeat collects Windows event logs on a Windows host. Inspect optional paths in CodeForge Stack lab, Fleet UI and container logs. [E1-E4]")
note("Interpretation.", "Observing the stack and indexing MyScoutee business data are distinct steps. The latter needs a data model, authorization rules and a deletion plan.", GOLD)

page("04 / Search", "MyScoutee: service offerings",
     "A concrete candidate for improving the current in-application search. Sources: ServiceOfferingsService, ServiceOfferingsRepository and ServiceOfferingsController. [M1]")
heading("Current behavior")
para("<b>ServiceOfferingsService.page</b> loads offerings from MongoDB and then filters in a Java stream by status, category, and substring matches in title and description. It subsequently evaluates profiles, distance, language and visibility, sorts results and paginates. The <b>discover</b> path limits results to published offerings and excludes the actor's own offering.")
heading("Proposed search index boundary")
flow([("MongoDB", "offering ID,<br/>version and state"), ("Projector", "publish / update /<br/>delete events"), ("Elasticsearch", "title, description,<br/>category, language, geo")],
     "Figure 3. The index is a proposed read model. MongoDB remains authoritative for writes and access decisions.")
table([
    ["<b>Experiment</b>", "<b>Potential value</b>", "<b>Condition</b>"],
    ["Relevance, typo tolerance, autocomplete", "Better ranking for title and description queries", "Measure against a real query corpus"],
    ["Category + distance + language", "Filter candidates in one search query", "Recheck existing visibility rules"],
    ["Facets and aggregations", "Explore demand and category trends", "Do not expose personal data in statistics"],
], [.27, .36, .37], 6)
note("Possible replacement.", "An indexed candidate search could replace the Java substring filter and in-memory sorting of the full offering list. It cannot replace MongoDB storage or the existing profile and access policies.", GOLD)
para("<b>Try it now:</b> the saved service discovery dashboard, published-offerings Discover session and offering map use the same 64 fictional listings. The coordinates represent example city locations, not MyScoutee users.", "small", 5)

page("05 / Observability", "MyScoutee: outbox and audit",
     "Operational visibility can be added at existing ownership boundaries. Sources: NotificationOutboxWorkerService and EventTicketAuditService. [M2-M3]")
heading("Notification outbox")
para("<b>NotificationOutboxWorkerService</b> watches Mongo change streams and handles due work, leases, retries, delivery windows and Firebase delivery. A trial Elastic stream should contain only structured, minimized transitions: <b>rule_key, status, attempt, latency_ms, error_class, occurred_at</b>.")
para("Logstash or Elastic Agent could forward application JSON logs; Kibana can chart delayed and failed deliveries. Alerts could be assessed alongside existing <b>OperationalTelemetry</b>. Elastic is not the delivery queue and cannot replace the Mongo outbox, retry logic or Firebase integration.")
heading("Ticket check-in replay audit")
para("<b>EventTicketAuditService</b> already records repeated check-in attempts as <b>check-in-replay</b> and <b>already_used</b> in MongoDB. A filtered secondary index could support searches by event and time window and help investigate spikes in replay attempts.")
table([
    ["<b>Source data</b>", "<b>Proposed Elastic field</b>", "<b>Constraint</b>"],
    ["Audit identity", "audit_id, action, result", "Idempotent upsert / deduplication"],
    ["Event and time", "event_id, attempted_at", "Retention and access control"],
    ["Actor and ticket", "May be unnecessary", "Pseudonymization and authorization"],
], [.25, .37, .38], 6)
note("Possible replacement.", "Elastic/Kibana could replace ad hoc log searches and some administrative summaries after data quality and access checks. The primary Mongo audit record remains the owned evidence.", GOLD)
para("<b>Try it now:</b> the event reliability dashboard and retry Discover session use 96 synthetic records. A local Security query rule highlights replay failures without external notifications.", "small", 5)
para("<b>Elastic Defend dashboard:</b> four additional demo rules turn 32 synthetic endpoint-shaped signals into local Security alerts. The managed Endpoint Detection and Response dashboard then shows severity, MITRE, OS, host and user panels. Select Today if its 15-minute time range has expired. No host is protected by this fixture.", "small", 5)

page("06 / Decisions", "Integration decision gates",
     "This lab does not change the MyScoutee backend. The following order defines a measured integration trial rather than an unverified migration.")
table([
    ["<b>Gate</b>", "<b>Action</b>", "<b>Evidence</b>"],
    ["1. Data scope", "Choose one search or telemetry case and list required fields", "No accidental personal data or secrets"],
    ["2. Projection", "Emit owner-side change signals or use an idempotent projector", "Rebuild, deletion and version handling"],
    ["3. Authorization", "Check candidate IDs against existing policy; filter workspace/tenant", "Same visible result set as the current API"],
    ["4. Measurement", "Measure P95 latency, relevance, index lag and failures", "Compare with the current path"],
    ["5. Operations", "Plan backfill, DLQ, monitoring, retention and backup", "Lost or duplicate events handled"],
], [.16, .43, .41], 6)
heading("Suggested experiment order")
para("<b>First:</b> explore CodeForge and the prepared fictional offering, map and event views. <b>Second:</b> export a separate, non-production set of service offerings and measure search quality. <b>Third:</b> stream a minimal subset of outbox or ticket-audit event fields. Existing MyScoutee owners define the rules in every step.")
note("Critical risk.", "An Elasticsearch index may lag or be incomplete. User-visible search results must retain the current access check, and the fallback for a missing index must be defined.", GOLD)

page("07 / Exercises", "Exercises and evidence",
     "Each exercise connects a component to an observable result. Check returned fields and document counts, not only whether a container is Up.")
table([
    ["<b>Exercise</b>", "<b>Expected evidence</b>"],
    ["Search outbox in CodeForge", "Source excerpts and related hits in forge-files"],
    ["Filter by language, module and severity", "Aggregated count; finding review state can change"],
    ["Rescan and inspect forge-activity", "scan_completed event with a Logstash-processed timestamp"],
    ["Request CodeForge and Kibana over HTTP", "heartbeat-* monitor event with up/down state"],
    ["Inspect cluster and index metrics", "metricbeat-* document"],
    ["Open saved offering map and charts", "Geo points, city/category facets and reusable library visuals"],
    ["Open synthetic replay rule", "Rule queries demo events; no external action is configured"],
    ["Open managed Elastic Defend dashboard", "32 synthetic endpoint alerts fill the EDR panels; no protected host"],
    ["Start optional Agent, Auditbeat and Packetbeat", "Each path has documents in its own index"],
], [.49, .51], 6)
heading("Quick diagnosis")
code(["docker compose --env-file .local/core.env ps -a", "docker compose --env-file .local/core.env logs --tail=60 \\", "  logstash filebeat metricbeat heartbeat"])
para("If <b>forge-activity</b> is empty, inspect the CodeForge JSONL log and Filebeat's connection to Logstash port 5044. Optional profiles start separately. <b>docker compose down -v</b> deletes local indexes, so use it only when you want to discard them.")
para("On the managed <b>[Elastic Security] Detection rule monitoring</b> dashboard, a <b>(null)</b> Warning or Failed card means its filter found no matching status changes in the selected time range. Treat it as zero for that status. Succeeded runs are genuine; the lab does not inject failing rules to fill these cards.", "small", 5)
note("Completion check.", "The core path (source -&gt; search), log path (Filebeat -&gt; Logstash -&gt; search) and telemetry paths (Metricbeat and Heartbeat) must all yield retrievable documents.")

page("08 / Sources", "Sources and validity",
     "MyScoutee findings reflect the local checkout on 27 October 2026. The integration diagrams are proposals, not completed backend changes.")
heading("MyScoutee source locations")
para("<b>[M1]</b> <font name='Mono' size='7'>server/projects/profile/src/main/java/com/raxim/myscoutee/domain/community/service/ServiceOfferingsService.java</font>; also <b>repository/ServiceOfferingsRepository.java</b> and <b>controller/ServiceOfferingsController.java</b>.", "small")
para("<b>[M2]</b> <font name='Mono' size='7'>server/projects/profile/src/main/java/com/raxim/myscoutee/domain/notifications/service/NotificationOutboxWorkerService.java</font>.", "small")
para("<b>[M3]</b> <font name='Mono' size='7'>server/projects/profile/src/main/java/com/raxim/myscoutee/domain/events/service/EventTicketAuditService.java</font>.", "small")
heading("Primary Elastic documentation")
para("<b>[E1]</b> Logstash Docker: https://www.elastic.co/docs/reference/logstash/docker-config", "small")
para("<b>[E2]</b> Filebeat Docker: https://www.elastic.co/docs/reference/beats/filebeat/running-on-docker", "small")
para("<b>[E3]</b> Elastic Agent containers: https://www.elastic.co/docs/reference/fleet/elastic-agent-container", "small")
para("<b>[E4]</b> Fleet Server prerequisites: https://www.elastic.co/docs/reference/fleet/add-fleet-server-on-prem", "small")
para("<b>[E5]</b> Dashboards as code: https://www.elastic.co/docs/explore-analyze/dashboards/create-dashboards-programmatically", "small")
para("<b>[E6]</b> Endpoint Detection and Response dashboard: https://www.elastic.co/docs/solutions/security/dashboards/endpoint-detection-response-dashboard", "small")
para("<b>[E7]</b> Elastic Defend integration: https://www.elastic.co/docs/reference/integrations/endpoint", "small")
para("<b>[E8]</b> Monitor rule executions: https://www.elastic.co/docs/solutions/security/detect-and-alert/monitor-rule-executions", "small")
heading("Repository entry points")
para("<b>README.md</b> explains startup and components; <b>compose.yaml</b> defines profiles; <b>config/</b> contains ingest and telemetry settings. The editable PDF source is <b>guides/build_elastic_guide.py</b>.")
note("Security boundary.", "Core Elasticsearch, Kibana, CodeForge and collectors require credentials. The EDR dashboard uses synthetic alerts from demo-* hosts, not a real Elastic Defend installation. Container traffic remains HTTP without TLS; published ports bind to localhost. Winlogbeat requires Windows. Production needs stronger identity and transport security.", GOLD)

assert n == TOTAL
c.save()
print(OUT)
