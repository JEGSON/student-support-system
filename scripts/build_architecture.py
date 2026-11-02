import html
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "docs/architecture"
ASSETS = OUT / "architecture-previews"
ASSETS.mkdir(exist_ok=True)
W, H = 1600, 1080
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
pal = {
    "app": ("#e7f1fa", "#30658a"),
    "data": ("#e8f3ec", "#37704b"),
    "external": ("#f1edf8", "#715497"),
    "actor": ("#fff1db", "#936626"),
    "note": ("#fff9e8", "#a3852d"),
    "zone": ("#f5f7fa", "#9aaab7"),
}
pages = []


class Page:
    def __init__(self, title, subtitle):
        self.title = title
        self.subtitle = subtitle
        self.nodes = []
        self.edges = []
        self.zones = []
        pages.append(self)

    def box(self, id, x, y, w, h, title, body="", kind="app"):
        self.nodes.append(dict(id=id, x=x, y=y, w=w, h=h, title=title, body=body, kind=kind))
        return id

    def zone(self, id, x, y, w, h, title):
        self.zones.append(dict(id=id, x=x, y=y, w=w, h=h, title=title))

    def edge(self, a, b, label="", side="right", target="left", via=None, dash=False):
        self.edges.append(
            dict(a=a, b=b, label=label, side=side, target=target, via=via or [], dash=dash)
        )

    def note(self, text):
        self.box("note", 50, 950, 1500, 85, "Reading this diagram", text, "note")


p = Page(
    "01 System context",
    "One fictional UK university • people, system responsibilities and external dependencies",
)
p.box(
    "student",
    60,
    190,
    300,
    150,
    "Student",
    "Submit support requests; track own cases; exchange messages.",
    "actor",
)
p.box(
    "staff",
    60,
    400,
    300,
    160,
    "Support staff and managers",
    "Triage, assign and manage authorised cases; arrange controlled referrals.",
    "actor",
)
p.box(
    "admin",
    60,
    640,
    300,
    150,
    "Administrator and reviewer",
    "Manage approved access or inspect audit scope. No routine case-content access.",
    "actor",
)
p.box(
    "system",
    580,
    350,
    420,
    250,
    "Student Support System",
    "Secure case management across finance, academic, wellbeing, disability and accommodation teams.",
    "app",
)
p.box(
    "idp",
    1200,
    180,
    330,
    150,
    "University identity provider",
    "Target integration: OpenID Connect; staff MFA and account lifecycle.",
    "external",
)
p.box(
    "email",
    1200,
    420,
    330,
    150,
    "Approved email provider",
    "Target integration: generic update alerts linking back to sign-in.",
    "external",
)
p.box(
    "owners",
    1200,
    670,
    330,
    150,
    "Institutional service owners",
    "Supply privacy, retention, safeguarding and operational policies.",
    "actor",
)
p.edge("student", "system", "Own cases", via=[(450, 265), (450, 410)], target="left")
p.edge("staff", "system", "Scoped case work")
p.edge("admin", "system", "Restricted administration", via=[(470, 715), (470, 555)])
p.edge("system", "idp", "Authenticate", via=[(1100, 475), (1100, 255)])
p.edge("system", "email", "Generic notifications")
p.edge(
    "owners",
    "system",
    "Policy / governance",
    side="left",
    target="bottom",
    via=[(1090, 745), (790, 745)],
    dash=True,
)
p.note(
    "Scope is one institution. Student-record integration, uploads, broad exports and automated risk scoring are deferred. This is a proposed design, not an existing university service."
)

p = Page(
    "02 Containers and trust boundaries",
    "Runtime responsibilities • arrows show principal data-flow direction, not every network exchange",
)
p.zone("private", 410, 170, 740, 690, "PRIVATE APPLICATION NETWORK")
p.box(
    "browser",
    50,
    210,
    290,
    140,
    "Browser",
    "Server-rendered HTML; CSRF-protected forms; opaque session cookie.",
    "actor",
)
p.box(
    "edge",
    50,
    470,
    290,
    130,
    "HTTPS edge",
    "TLS termination; request limits; approved hosts; trusted proxy configuration.",
)
p.box(
    "app",
    455,
    300,
    300,
    180,
    "Flask application / WSGI",
    "Routes → policy checks → services → repositories. No public database access.",
)
p.box(
    "db",
    825,
    300,
    280,
    180,
    "MongoDB replica set",
    "Business records, sessions, audit events and transactional outbox.",
    "data",
)
p.box(
    "worker",
    455,
    660,
    300,
    140,
    "Notification worker",
    "Lease jobs; resolve approved contact; send generic templates; bounded retries.",
)
p.box(
    "logs",
    825,
    660,
    280,
    140,
    "Operational logs",
    "Restricted metadata; metrics; alerts. No case narratives or secrets.",
    "data",
)
p.box(
    "idp",
    1220,
    180,
    300,
    140,
    "Identity provider",
    "Separate trust domain. Development substitute uses synthetic users.",
    "external",
)
p.box(
    "email",
    1220,
    460,
    300,
    140,
    "Email provider",
    "Separate trust domain; minimum necessary recipient information.",
    "external",
)
p.box(
    "backup",
    1220,
    720,
    300,
    140,
    "Backup storage",
    "Encrypted, isolated recovery copies; controlled key access and expiry.",
    "data",
)
p.edge("browser", "edge", "HTTPS", side="bottom", target="top")
p.edge("edge", "app", "Validated requests", via=[(385, 535), (385, 390)])
p.edge("app", "db", "Scoped reads / transactions")
p.edge("app", "idp", "OIDC exchange", side="top", via=[(605, 245), (1180, 245)])
p.edge(
    "db",
    "worker",
    "Lease jobs / contact only",
    side="bottom",
    target="right",
    via=[(965, 570), (790, 570), (790, 730)],
)
p.edge(
    "worker",
    "email",
    "Generic email",
    side="right",
    target="left",
    via=[(785, 850), (1170, 850), (1170, 530)],
)
p.edge("app", "logs", "Safe telemetry", side="bottom", target="top", via=[(605, 555), (965, 555)])
p.edge(
    "db",
    "backup",
    "Recovery copies",
    side="right",
    target="top",
    via=[(1180, 390), (1180, 685), (1370, 685)],
    dash=True,
)
p.note(
    "Trust boundaries: browser/edge, edge/application, application/database, external identity/email, and privileged operations. Physical networking does not replace per-request authorisation. Worker has no case-content read permission."
)

p = Page(
    "03 Application components",
    "Logical layers inside the Flask deployment • policy is enforced in services for every entry point",
)
p.zone("web", 40, 170, 1520, 160, "WEB AND PRESENTATION")
p.box(
    "routes",
    80,
    210,
    420,
    85,
    "Routes and forms",
    "Typed input; CSRF; safe redirects; size limits.",
)
p.box(
    "views",
    590,
    210,
    420,
    85,
    "Jinja views / response projections",
    "Explicit student vs staff fields; escaped plain text.",
)
p.box(
    "errors",
    1100,
    210,
    420,
    85,
    "Safe responses",
    "Consistent denials; no-store; safe error pages.",
)
p.zone("service", 40, 400, 1520, 300, "APPLICATION SERVICES AND POLICY")
p.box(
    "policy",
    80,
    445,
    330,
    210,
    "Identity and policy gateway",
    "Active account + action + case relationship + team membership + lifecycle state. Deny by default.",
)
p.box("case", 470, 445, 300, 100, "Case services", "Submission; assignment; state transitions.")
p.box(
    "comm", 470, 570, 300, 100, "Communication services", "Student messages; protected staff notes."
)
p.box(
    "ref",
    820,
    445,
    300,
    100,
    "Referral service",
    "Explicit summary; approval; separate target case.",
)
p.box(
    "admin",
    820,
    570,
    300,
    100,
    "Access administration",
    "Separate approver; controlled grants / revocation.",
)
p.box(
    "unit",
    1180,
    445,
    330,
    225,
    "Transaction coordinator",
    "Version guard; case changes + business history + audit + outbox commit together. No email call inside transaction.",
)
p.box(
    "repo",
    480,
    775,
    580,
    110,
    "Repositories → private MongoDB",
    "Allowlisted filters; scoped queries; validators; indexes; session and audit persistence.",
    "data",
)
p.edge(
    "routes",
    "policy",
    "Authenticate / validate",
    side="bottom",
    target="top",
    via=[(290, 370), (245, 370)],
)
p.edge("policy", "case", "Authorise")
p.edge("policy", "comm", "Authorise", via=[(440, 550), (440, 620)])
p.edge(
    "case",
    "unit",
    "Mutate atomically",
    side="right",
    target="top",
    via=[(790, 495), (790, 380), (1345, 380)],
)
p.edge("unit", "repo", "Persist", side="bottom", target="right", via=[(1345, 830)])
p.edge(
    "repo",
    "views",
    "Read → safe projection",
    side="left",
    target="bottom",
    via=[(445, 830), (445, 365), (800, 365)],
    dash=True,
)
p.note(
    "Service modules share the same policy and persistence conventions. Diagram arrows illustrate the principal path; communication, referral and administration mutations also use the transaction coordinator. Route checks alone are insufficient."
)

p = Page(
    "04 Deployment and delivery",
    "Environment separation and release path • target production topology, not a deployed system",
)
p.zone("dev", 45, 180, 420, 660, "DEVELOPMENT")
p.zone("test", 525, 180, 440, 660, "TEST / STAGING")
p.zone("prod", 1025, 180, 530, 660, "PRODUCTION TARGET")
p.box(
    "local",
    85,
    230,
    340,
    140,
    "Developer environment",
    "Flask app + worker + local replica set + development identity provider. Synthetic data only.",
)
p.box(
    "git",
    85,
    510,
    340,
    140,
    "GitHub repository",
    "Source; design; tests; configuration examples; AI statement. No secrets.",
    "external",
)
p.box(
    "ci",
    575,
    230,
    340,
    140,
    "CI verification",
    "Tests; dependency / secret scans; reproducible artefact; recorded commit.",
)
p.box(
    "stage",
    575,
    510,
    340,
    160,
    "Isolated test deployment",
    "Real test replica set; synthetic users; email capture; browser / load / recovery tests.",
)
p.box("edge", 1080, 220, 420, 90, "HTTPS edge", "Approved public entry point; HTTPS only.")
p.box(
    "apps",
    1080,
    360,
    420,
    110,
    "Application instance(s) + worker",
    "Gunicorn; shared sessions / limits; separate worker credentials.",
)
p.box(
    "cluster",
    1080,
    525,
    420,
    110,
    "Private database replica set",
    "Separate credentials; validators; restricted network.",
    "data",
)
p.box(
    "ops",
    1080,
    690,
    420,
    110,
    "Protected operations",
    "Backups; secret manager; monitoring; incident ownership.",
    "data",
)
p.edge("local", "git", "Reviewed commits", side="bottom", target="top")
p.edge("git", "ci", "Run local checks", via=[(495, 580), (495, 300)])
p.edge("ci", "stage", "Deploy test artefact", side="bottom", target="top")
p.edge("stage", "apps", "Approved release only", via=[(995, 590), (995, 415)], dash=True)
p.edge("edge", "apps", "Forward requests", side="bottom", target="top")
p.edge("apps", "cluster", "TLS / least privilege", side="bottom", target="top")
p.edge("cluster", "ops", "Backup / metrics", side="bottom", target="top", dash=True)
p.note(
    "Production release requires operational and institutional readiness. Multi-node production replica placement must span failure domains; a single local replica-set node only enables development transactions. External identity/email providers are shown on page 02."
)

p = Page(
    "05 Business data relationships",
    "Logical MongoDB model • references are enforced by services, not relational foreign keys",
)
p.box(
    "user",
    50,
    190,
    330,
    155,
    "USERS",
    "id; issuer + subject [unique]\nstudent_reference; status; optional course",
    "data",
)
p.box("team", 635, 190, 330, 155, "TEAMS", "id; name [unique]\ncategory_scope; active", "data")
p.box(
    "member",
    1210,
    190,
    330,
    155,
    "MEMBERSHIPS",
    "user_id + team_id + role [unique]\nactive; granted_by; revoked_at",
    "data",
)
p.box(
    "case",
    610,
    435,
    380,
    220,
    "CASES",
    "id; reference [unique]; student_id\nteam_id; assignee_id; status\ncategory; description; version\npriority; closure; retention; hold",
    "data",
)
p.box(
    "msg",
    50,
    455,
    330,
    155,
    "MESSAGES",
    "case_id; author_id; body\ncreated_at; correction_of\nStudent-visible communication",
    "data",
)
p.box(
    "noteentity",
    1210,
    455,
    330,
    155,
    "INTERNAL NOTES",
    "case_id; author_id; body\ncreated_at; supersedes_id\nSeparate staff-only retrieval",
    "data",
)
p.box(
    "event",
    50,
    735,
    330,
    155,
    "CASE EVENTS",
    "case_id; actor_id; event_type\nallowlisted change metadata\nBusiness history",
    "data",
)
p.box(
    "ref",
    610,
    735,
    380,
    155,
    "REFERRALS",
    "source_case_id; target_team_id\nshared_summary; approvals\ntarget_case_id on acceptance",
    "data",
)
p.box(
    "key",
    1210,
    735,
    330,
    155,
    "SUBMISSION KEYS",
    "user + operation + key [unique]\nresult_id; expires_at\nRepeat-safe creation",
    "data",
)
p.edge(
    "user", "case", "1 owner → 0..* cases", side="bottom", via=[(215, 390), (560, 390), (560, 545)]
)
p.edge("team", "case", "1 team → 0..* cases", side="bottom", target="top")
p.edge("team", "member", "1 → 0..*")
p.edge(
    "user",
    "member",
    "1 user → 0..* memberships",
    side="top",
    target="top",
    via=[(215, 155), (1375, 155)],
)
p.edge("case", "msg", "1 case → 0..*", side="left", target="right")
p.edge("case", "noteentity", "1 case → 0..*")
p.edge(
    "case",
    "event",
    "1 case → 0..*",
    side="bottom",
    target="right",
    via=[(550, 700), (440, 700), (440, 810)],
)
p.edge("case", "ref", "1 source → 0..* referrals", side="bottom", target="top")
p.edge(
    "key",
    "case",
    "result references case",
    side="top",
    target="right",
    via=[(1375, 680), (1060, 680), (1060, 600)],
    dash=True,
)
p.note(
    "Other references: cases.assignee_id → users (0..1); message/note/event actors → users; referrals.target_case_id → a separate case (0..1). Acceptance must not grant access to source notes. Index lists and retention rules are in the design baseline."
)

p = Page(
    "06 Security and operational data",
    "Accountability, sessions and reliable notifications • data access is separated by purpose",
)
p.box(
    "user",
    50,
    200,
    330,
    160,
    "USERS",
    "Internal identity and current account status. Memberships determine current staff scope.",
    "data",
)
p.box(
    "session",
    635,
    200,
    330,
    160,
    "SESSIONS",
    "token_hash [unique]; user_id\nidle and absolute expiry; revoked_at\nNo case content in cookies",
    "data",
)
p.box(
    "browser",
    1210,
    200,
    330,
    160,
    "BROWSER COOKIE",
    "Opaque random token only\nSecure; HttpOnly; SameSite=Lax\nExplicit CSRF protection",
    "actor",
)
p.box(
    "case",
    50,
    480,
    330,
    170,
    "CASE TRANSACTION",
    "Business change + case event\n+ audit event + outbox job\nCommit or roll back together",
)
p.box(
    "audit",
    635,
    480,
    330,
    170,
    "AUDIT EVENTS",
    "actor; action; target; outcome\nrequest_id; occurred_at\nNo free-text narrative",
    "data",
)
p.box(
    "outbox",
    1210,
    480,
    330,
    170,
    "NOTIFICATION OUTBOX",
    "event key [unique per recipient/channel]\nstate; lease; retry count\nGeneric template only",
    "data",
)
p.box(
    "review",
    635,
    760,
    330,
    135,
    "AUDIT REVIEWER",
    "Approved read scope; purpose recorded. No audit mutation.",
    "actor",
)
p.box(
    "worker",
    1210,
    760,
    330,
    135,
    "RESTRICTED WORKER",
    "Lease jobs; resolve contact; send; mark outcome. No narrative read.",
)
p.box(
    "backup",
    50,
    760,
    330,
    135,
    "RECOVERY CONTROLS",
    "Encrypted backups; restore tests; reapply disposal; invalidate restored sessions.",
    "data",
)
p.edge("user", "session", "1 user → 0..* sessions")
p.edge("browser", "session", "Token lookup", side="left", target="right")
p.edge("case", "audit", "Append evidence")
p.edge(
    "case", "outbox", "Enqueue atomically", side="top", target="top", via=[(215, 420), (1375, 420)]
)
p.edge("audit", "review", "Approved read", side="bottom", target="top")
p.edge("outbox", "worker", "Lease / retry", side="bottom", target="top")
p.edge(
    "user",
    "worker",
    "Resolve approved contact",
    side="left",
    target="bottom",
    via=[(25, 280), (25, 925), (1375, 925)],
    dash=True,
)
p.edge("case", "backup", "Recovery coverage", side="bottom", target="top", dash=True)
p.note(
    "Required read audits must persist before sensitive content is returned. TTL cleanup never substitutes for expiry checks. Outbox delivery is at least once; a crash after sending can create a duplicate. Audit protection is not a claim of immunity to privileged infrastructure compromise."
)

p = Page(
    "07 Case workflow and controlled referral",
    "Business transitions • separate role gates and referral lifecycle from case status",
)
p.box(
    "submit",
    50,
    200,
    280,
    130,
    "Student submits",
    "Owner and timestamps set by server. Category maps to accountable team.",
    "actor",
)
p.box(
    "new",
    430,
    200,
    280,
    130,
    "NEW",
    "Manager assigns eligible officer. Assignment alone does not start work.",
)
p.box(
    "progress",
    830,
    200,
    280,
    130,
    "IN PROGRESS",
    "Assigned officer or scoped manager handles the case.",
)
p.box(
    "await",
    1230,
    200,
    280,
    130,
    "AWAITING STUDENT",
    "Staff post a visible request for information.",
)
p.box(
    "closed",
    830,
    480,
    280,
    145,
    "CLOSED",
    "Resolution required. Manager may reopen with reason and valid assignment.",
)
p.box(
    "archive",
    430,
    480,
    280,
    145,
    "ARCHIVED FLAG",
    "Separate lifecycle attribute. Retention review and legal-hold checks.",
    "data",
)
p.box(
    "dispose",
    50,
    480,
    280,
    145,
    "DISPOSAL",
    "Approved policy function; linked data and backup lifecycle considered.",
    "data",
)
p.box(
    "proposal",
    50,
    760,
    390,
    140,
    "1 Propose referral",
    "Assigned officer provides purpose and selected summary; source manager approves.",
)
p.box(
    "decision",
    605,
    760,
    390,
    140,
    "2 Target manager decides",
    "Only approved proposal information is visible. Accept or reject with recorded decision.",
)
p.box(
    "targetcase",
    1160,
    760,
    390,
    140,
    "3 Separate target case",
    "Acceptance creates New case in target team. No inherited source-note access.",
)
p.edge("submit", "new", "Create")
p.edge("new", "progress", "Start work")
p.edge("progress", "await", "Ask student")
p.edge(
    "await",
    "progress",
    "Student reply",
    side="bottom",
    target="bottom",
    via=[(1370, 390), (970, 390)],
)
p.edge("progress", "closed", "Resolve", side="bottom", target="top")
p.edge("closed", "archive", "Policy review", side="left", target="right")
p.edge("archive", "dispose", "Retention / no hold", side="left", target="right")
p.edge("proposal", "decision", "Approved summary")
p.edge("decision", "targetcase", "Accept atomically")
p.note(
    "Reopening: Closed → In Progress is manager-only and audited. Awaiting Student must return to In Progress before closure; no automatic closure for silence in v1. Referral leaves source status unchanged. Urgent-help and operating-hours procedures remain institutional approval gates."
)

p = Page(
    "08 Case submission sequence",
    "Successful path plus failure guarantees • database transaction excludes external email calls",
)
actors = [
    ("student", "Student browser", 60),
    ("web", "Flask route", 360),
    ("svc", "Policy / service", 660),
    ("db", "MongoDB", 960),
    ("worker", "Worker / email", 1260),
]
for id, title, x in actors:
    p.box(id, x, 175, 250, 80, title, "", "data" if id == "db" else "app")
for _i, (a, b, label, y) in enumerate(
    [
        ("student", "web", "1 POST form + CSRF + submission key", 320),
        ("web", "svc", "2 Validate session, owner and typed input", 395),
        ("svc", "db", "3 Check key; begin transaction", 470),
        ("svc", "db", "4 Insert case + event + audit + outbox", 545),
        ("db", "svc", "5 Commit or abort", 620),
        ("svc", "web", "6 Return existing/new case reference", 695),
        ("web", "student", "7 Redirect to authorised own-case view", 770),
        ("db", "worker", "8 Worker leases committed job; sends alert", 845),
    ]
):
    # Sequence messages use explicit endpoints, with matching draw.io free points.
    p.edges.append(
        dict(
            a=a, b=b, label=label, side="bottom", target="bottom", via=[], dash=False, sequence_y=y
        )
    )
p.note(
    "If validation or authorisation fails: no transaction. If audit/outbox write fails: roll back case creation. Retry with same key returns one result. If email fails: case remains saved; retry delivery. If response is lost after commit: same key recovers the saved reference."
)


# Reconcile the original native model with the implemented local demonstration.
def revise(page, node, title, body):
    item = next(n for n in pages[page - 1].nodes if n["id"] == node)
    item.update(title=title, body=body)


revise(
    1,
    "idp",
    "Identity provider",
    "Local OIDC/PKCE and synthetic student signup. University identity/MFA integration remains unapproved.",
)
revise(
    1,
    "email",
    "Email delivery",
    "Mailpit loopback capture only. Generic messages; real external delivery disabled.",
)
revise(
    1,
    "note",
    "Implementation scope",
    "Local synthetic application implemented. Institutional policies, real-data processing and public deployment remain blocked. Uploads/exports/migration/risk scoring deferred.",
)
revise(
    2,
    "edge",
    "HTTPS edge template",
    "Exact one-hop proxy controls prepared and tested. No public production deployment.",
)
revise(
    2,
    "backup",
    "Recovery quarantine",
    "Encrypted snapshots + separate key file. Restore DB isolated; disposal ledger replay; no stale notifications.",
)
revise(
    3,
    "note",
    "Implemented boundaries",
    "Server services enforce current permissions and transactions. DB identities separate web, worker, audit reader, maintenance and restore access. No real university integration.",
)
revise(
    4,
    "git",
    "Local Git / configured remote",
    "Meaningful local commits and evidence. GitHub origin configured; no remote push or remote history claim.",
)
revise(
    4,
    "ci",
    "Local verification / package",
    "Unit, real DB and browser/security checks; reproducible ZIP. Remote CI is not claimed.",
)
revise(
    4,
    "stage",
    "Isolated local evaluation",
    "Synthetic replica set + identity + capture. Browser, 15-minute workload and encrypted restore measured.",
)
revise(
    4,
    "ops",
    "Production operations pending",
    "KMS separation; backup cadence; monitoring/on-call and institutional ownership require approval.",
)
revise(
    5,
    "user",
    "USERS",
    "issuer + subject; account status\nPreferred name/course; profile_version\nAccount guard; controlled staff grants",
)
revise(
    5,
    "ref",
    "REFERRALS",
    "source/target teams + category\nMinimal summary; manager decisions\nSeparate target case on acceptance",
)
revise(
    5,
    "key",
    "SUBMISSION KEYS",
    "user + operation + key hash [unique]\npayload hash; result_id; expiry\nNo narrative; same-key retries",
)
revise(
    6,
    "session",
    "SESSIONS / AUTH ATTEMPTS",
    "Hashed opaque token; server state\nIdle/absolute expiry; revocation\n10-minute OIDC nonce/PKCE state",
)
revise(
    6,
    "browser",
    "BROWSER / SHARED LIMITS",
    "Opaque HttpOnly cookie + CSRF\nMongo rate counters / TTL cleanup\nSecure cookie required in production",
)
revise(
    6,
    "review",
    "SCOPED AUDIT REVIEW",
    "Approved case/team scope and purpose. Separate read credential; append-only evidence.",
)
revise(
    6,
    "backup",
    "RECOVERY / DISPOSAL",
    "Encrypted snapshot; restore quarantine\nDurable disposal ledger replay\nInvalidate sessions; suppress jobs",
)
revise(
    6,
    "note",
    "18 collection contracts",
    "Additional guard data: memberships, privileged grants, triage claims, service principals, disposal ledger and rate limits. Synthetic one-day retention only; no real duration approved.",
)
revise(
    7,
    "dispose",
    "SYNTHETIC DISPOSAL",
    "One-day test policy only; hold checks; separate approval; offline executor and durable ledger.",
)
pages[
    3
].subtitle = "Implemented local verification; production topology remains a reviewed template, not a deployed service"
for page in pages:
    page.subtitle += " • local demo v2"


def anchor(n, side):
    return {
        "left": (n["x"], n["y"] + n["h"] / 2),
        "right": (n["x"] + n["w"], n["y"] + n["h"] / 2),
        "top": (n["x"] + n["w"] / 2, n["y"]),
        "bottom": (n["x"] + n["w"] / 2, n["y"] + n["h"]),
    }[side]


mx = ET.Element(
    "mxfile",
    host="app.diagrams.net",
    modified="2026-11-02T00:00:00.000Z",
    agent="Codex",
    version="24.7.17",
    type="device",
)
for idx, p in enumerate(pages, 1):
    diag = ET.SubElement(mx, "diagram", id=f"page-{idx}", name=p.title)
    model = ET.SubElement(
        diag,
        "mxGraphModel",
        dx="1600",
        dy="1080",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="1",
        pageScale="1",
        pageWidth=str(W),
        pageHeight=str(H),
        math="0",
        shadow="0",
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    def vertex(id, value, x, y, w, h, style, root=root):
        c = ET.SubElement(root, "mxCell", id=id, value=value, style=style, vertex="1", parent="1")
        ET.SubElement(
            c,
            "mxGeometry",
            x=str(x),
            y=str(y),
            width=str(w),
            height=str(h),
            attrib={"as": "geometry"},
        )

    vertex(
        "title",
        p.title,
        45,
        30,
        1510,
        55,
        "text;html=0;align=left;verticalAlign=middle;fontSize=30;fontStyle=1;fontColor=#172b3a;",
    )
    vertex(
        "subtitle",
        p.subtitle,
        45,
        95,
        1510,
        45,
        "text;html=0;align=left;verticalAlign=middle;fontSize=17;fontColor=#526574;whiteSpace=wrap;",
    )
    for z in p.zones:
        vertex(
            z["id"],
            z["title"],
            z["x"],
            z["y"],
            z["w"],
            z["h"],
            "rounded=1;html=0;verticalAlign=top;align=left;spacingTop=12;spacingLeft=14;fontSize=14;fontStyle=1;fillColor=#f5f7fa;strokeColor=#9aaab7;dashed=1;",
        )
    nodes = {n["id"]: n for n in p.nodes}
    for n in p.nodes:
        fill, stroke = pal[n["kind"]]
        vertex(
            n["id"],
            n["title"] + "\n\n" + n["body"],
            n["x"],
            n["y"],
            n["w"],
            n["h"],
            f"rounded=1;html=0;whiteSpace=wrap;align=left;verticalAlign=middle;spacing=15;fontSize=16;fillColor={fill};strokeColor={stroke};strokeWidth=1.5;",
        )
    for j, e in enumerate(p.edges):
        special = "sequence_y" in e
        exits = {
            "right": ("1", "0.5"),
            "left": ("0", "0.5"),
            "top": ("0.5", "0"),
            "bottom": ("0.5", "1"),
        }
        ex, ey = exits[e["side"]]
        ix, iy = exits[e["target"]]
        attrs = dict(
            id=f"edge-{j}",
            value=e["label"],
            style=f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;endArrow=block;endFill=1;strokeColor=#526574;strokeWidth=1.5;fontSize=14;labelBackgroundColor=#ffffff;dashed={int(e['dash'])};exitX={ex};exitY={ey};entryX={ix};entryY={iy};",
            edge="1",
            parent="1",
        )
        if not special:
            attrs.update(source=e["a"], target=e["b"])
        c = ET.SubElement(root, "mxCell", **attrs)
        g = ET.SubElement(c, "mxGeometry", relative="1", attrib={"as": "geometry"})
        if special:
            for key, id in [("sourcePoint", e["a"]), ("targetPoint", e["b"])]:
                n = nodes[id]
                ET.SubElement(
                    g,
                    "mxPoint",
                    x=str(n["x"] + n["w"] / 2),
                    y=str(e["sequence_y"]),
                    attrib={"as": key},
                )
        if e["via"]:
            ar = ET.SubElement(g, "Array", attrib={"as": "points"})
            for x, y in e["via"]:
                ET.SubElement(ar, "mxPoint", x=str(x), y=str(y))
    if idx == 8:
        for j, n in enumerate([n for n in p.nodes if n["id"] != "note"]):
            c = ET.SubElement(
                root,
                "mxCell",
                id=f"lifeline-{j}",
                style="endArrow=none;dashed=1;strokeColor=#9aaab7;",
                edge="1",
                parent="1",
            )
            g = ET.SubElement(c, "mxGeometry", relative="1", attrib={"as": "geometry"})
            for key, y in [("sourcePoint", 255), ("targetPoint", 900)]:
                ET.SubElement(
                    g, "mxPoint", x=str(n["x"] + n["w"] / 2), y=str(y), attrib={"as": key}
                )
    vertex(
        "footer",
        f"COM7033 | Local implementation v2.0 / production target | 2 November 2026 | {idx:02d} / {len(pages):02d}",
        50,
        1045,
        1500,
        25,
        "text;html=0;align=left;fontSize=12;fontColor=#526574;",
    )

ET.indent(mx)
ET.ElementTree(mx).write(
    OUT / "student-support-architecture.drawio", encoding="utf-8", xml_declaration=True
)


# PNG previews are generated from the same diagram model. draw.io remains the editable source.
def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def wrap(draw, txt, f, maxw):
    lines = []
    for para in txt.split("\n"):
        current = ""
        for word in para.split():
            test = (current + " " + word).strip()
            if draw.textlength(test, font=f) > maxw and current:
                lines.append(current)
                current = word
            else:
                current = test
        lines.append(current)
    return lines


for idx, p in enumerate(pages, 1):
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.text((45, 30), p.title, font=font(30, True), fill="#172b3a")
    d.text((45, 95), p.subtitle, font=font(17), fill="#526574")
    for z in p.zones:
        d.rounded_rectangle(
            (z["x"], z["y"], z["x"] + z["w"], z["y"] + z["h"]),
            12,
            fill="#f5f7fa",
            outline="#9aaab7",
            width=2,
        )
        d.text((z["x"] + 14, z["y"] + 12), z["title"], font=font(14, True), fill="#526574")
    nodes = {n["id"]: n for n in p.nodes}
    if idx == 8:
        for n in p.nodes:
            if n["id"] == "note":
                continue
            x = n["x"] + n["w"] / 2
            for y in range(255, 900, 14):
                d.line((x, y, x, y + 7), fill="#9aaab7", width=1)
    # Draw connectors beneath boxes; labels above connectors and below boxes.
    labels = []
    for e in p.edges:
        if "sequence_y" in e:
            a = nodes[e["a"]]
            b = nodes[e["b"]]
            pts = [(a["x"] + a["w"] / 2, e["sequence_y"]), (b["x"] + b["w"] / 2, e["sequence_y"])]
        else:
            a = anchor(nodes[e["a"]], e["side"])
            b = anchor(nodes[e["b"]], e["target"])
            pts = [a] + e["via"] + [b]
            if len(pts) == 2 and a[0] != b[0] and a[1] != b[1]:
                mid = (a[0] + b[0]) / 2
                pts = [a, (mid, a[1]), (mid, b[1]), b]
        for a, b in zip(pts, pts[1:], strict=False):
            if e["dash"]:
                length = math.dist(a, b)
                for t in range(0, int(length), 14):
                    u = t / max(length, 1)
                    v = min(t + 7, length) / max(length, 1)
                    d.line(
                        (
                            a[0] + (b[0] - a[0]) * u,
                            a[1] + (b[1] - a[1]) * u,
                            a[0] + (b[0] - a[0]) * v,
                            a[1] + (b[1] - a[1]) * v,
                        ),
                        fill="#526574",
                        width=2,
                    )
            else:
                d.line([a, b], fill="#526574", width=2)
        a, b = pts[-2:]
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        d.polygon(
            [
                b,
                (b[0] - 12 * math.cos(ang - 0.4), b[1] - 12 * math.sin(ang - 0.4)),
                (b[0] - 12 * math.cos(ang + 0.4), b[1] - 12 * math.sin(ang + 0.4)),
            ],
            fill="#526574",
        )
        horizontal = [(a, b) for a, b in zip(pts, pts[1:], strict=False) if abs(a[1] - b[1]) < 1]
        seg = max(
            horizontal or list(zip(pts, pts[1:], strict=False)), key=lambda ab: math.dist(*ab)
        )
        a, b = seg
        f = font(13)
        maxw = max(65, min(340, math.dist(a, b) - 10))
        lines = wrap(d, e["label"], f, maxw)
        if abs(a[1] - b[1]) < 1:
            x = (a[0] + b[0]) / 2
            y = (a[1] + b[1]) / 2 - len(lines) * 16 - 3
        else:
            x = a[0] + 8 + max(d.textlength(line, font=f) for line in lines) / 2
            y = (a[1] + b[1]) / 2 - len(lines) * 8
        labels.append((x, y, lines))
    for x, y, lines in labels:
        f = font(13)
        for line in lines:
            width = d.textlength(line, font=f)
            d.rectangle((x - width / 2 - 3, y - 1, x + width / 2 + 3, y + 16), fill="white")
            d.text((x - width / 2, y), line, font=f, fill="#384e5c")
            y += 16
    for n in p.nodes:
        fill, stroke = pal[n["kind"]]
        x, y, w, h = [n[k] for k in ["x", "y", "w", "h"]]
        d.rounded_rectangle((x, y, x + w, y + h), 10, fill=fill, outline=stroke, width=2)
        fs = 16
        titlelines = wrap(d, n["title"], font(fs, True), w - 30)
        bodylines = wrap(d, n["body"], font(fs), w - 30)
        needed = len(titlelines) * 21 + len(bodylines) * 21 + 12
        while needed > h - 24 and fs > 12:
            fs -= 1
            titlelines = wrap(d, n["title"], font(fs, True), w - 30)
            bodylines = wrap(d, n["body"], font(fs), w - 30)
            needed = (len(titlelines) + len(bodylines)) * (fs + 5) + 12
        assert needed <= h - 18, (p.title, n["id"], needed, h)
        yy = y + max(12, (h - needed) / 2)
        for line in titlelines:
            d.text((x + 15, yy), line, font=font(fs, True), fill="#172b3a")
            yy += fs + 5
        yy += 10
        for line in bodylines:
            d.text((x + 15, yy), line, font=font(fs), fill="#172b3a")
            yy += fs + 5
    d.text(
        (50, 1045),
        f"COM7033 | Local implementation v2.0 / production target | 2 November 2026 | {idx:02d} / {len(pages):02d}",
        font=font(12),
        fill="#526574",
    )
    im.save(ASSETS / f"{idx:02d}.png")

sections = "".join(
    f'<section id="page-{i}"><h2>{html.escape(p.title)}</h2><p>{html.escape(p.subtitle)}</p><a href="architecture-previews/{i:02d}.png"><img src="architecture-previews/{i:02d}.png" alt="{html.escape(p.title)}"></a></section>'
    for i, p in enumerate(pages, 1)
)
nav = " · ".join(
    f'<a href="#page-{i}">{i:02d} {html.escape(p.title[3:])}</a>' for i, p in enumerate(pages, 1)
)
(OUT / "architecture-overview.html").write_text(
    f"""<!doctype html><html lang="en-GB"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Student Support Architecture Diagrams</title><style>body{{font:16px/1.6 system-ui,sans-serif;color:#172b3a;background:#f1f5f7;margin:0}}main{{max-width:1500px;margin:auto;padding:32px}}section{{background:white;padding:24px;margin:28px 0;border:1px solid #d7e0e6;border-radius:10px}}img{{width:100%;height:auto}}a{{color:#125b70}}nav{{line-height:2.2}}@media print{{section{{break-before:page;padding:0;border:0}}nav{{display:none}}}}</style><main><h1>Student Support Architecture Diagrams</h1><p>Eight reconciled views of the implemented local synthetic Flask/MongoDB demonstration and its undeployed production target. See <a href="runtime-status.md">current implementation status</a>.</p><p><a href="student-support-architecture.drawio">Download the editable draw.io file</a> · <a href="student-support-secure-design.html">Read the detailed design baseline</a></p><p>In diagrams.net / draw.io, choose <strong>File → Open From → Device</strong> and select the .drawio file. Each numbered view is a separate editable page. Shapes, connectors and labels are native diagram elements. PNG previews below use the same diagram model; draw.io may wrap text differently.</p><nav>{nav}</nav>{sections}<p>Proposed integrations and operating policies require institutional review. Identity registration, lawful grounds, retention, safeguarding, hosting and production access owners remain open decisions in the design baseline.</p></main></html>"""
)

# Validate graph references, page identifiers and native XML structure.
tree = ET.parse(OUT / "student-support-architecture.drawio")
for dg in tree.getroot().findall("diagram"):
    cells = dg.findall("./mxGraphModel/root/mxCell")
    ids = [c.get("id") for c in cells]
    assert len(ids) == len(set(ids))
    for c in cells:
        for attr in ("source", "target", "parent"):
            if c.get(attr):
                assert c.get(attr) in ids, (dg.get("name"), attr, c.get(attr))
print(
    f"Created and structurally validated {len(pages)} editable pages and {len(pages)} PNG previews."
)
