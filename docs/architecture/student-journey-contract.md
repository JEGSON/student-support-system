# Stage 08 student journey and persistence contract

Historical stage checkpoint. For the completed local runtime and current additions,
see [as-built status](runtime-status.md) and [inventory](implementation-inventory.md).

2 November 2026. Implements WF-01 and the student portions of FR-02/03 using the
existing Flask → service/policy → repository → MongoDB architecture. Draw.io views
03/05/06/08 remain the reference topology and successful submission sequence.
No framework, trust boundary, external integration or production scope changed.

## HTTP surface and views

| Endpoint | Behaviour |
| --- | --- |
| GET /cases | Current student's active requests, 20 per page; fixed metadata projection and scoped signed cursor |
| GET /cases/new | Accessible form with CSRF and a signed user-bound random submission key; no draft DB write |
| POST /cases/new | Strict URL-encoded field allowlist; validate, transact, then 303 redirect to the recorded request |
| GET /cases/UUID | Ownership/archive-filtered detail; identical 404 for foreign, missing, malformed or archived case |

Anonymous access redirects to university sign-in. Student context and a current
active internal student role are required. Staff/admin context cannot reach these
pages. All queries bind ownership server-side. Templates receive explicit student
views only, not raw documents. List views contain reference/category/status/times;
detail adds only the initial request description. Messages, notes, staff-only
history, memberships, priority and other students' counts/content are absent. Those
later feature screens are not claimed implemented. Sensitive reads commit their
metadata audit before returning any content; audit failure yields a safe 503.

The form accepts exactly csrf_token, submission_key, category and description.
Categories are academic, finance, wellbeing, disability and accommodation; plain
text is required and limited to 10,000 characters after normalising line endings.
Unsupported control characters are rejected. The request form alone permits a
128 KiB encoded body so 10,000 four-byte Unicode characters fit browser form
encoding; other endpoints retain the 64 KiB cap. This override runs before CSRF
form parsing, and an oversized form still rejects with 413. CRLF/CR/LF become LF before storage
and payload hashing, so browser/API lost-response retries agree. Jinja escapes
accepted script-like text; no unsafe marking, scripts or client draft persistence.
Inline errors, summary links and labels accompany 422 validation responses.
Missing/invalid CSRF or signed keys, JSON/operator shapes, duplicate fields and
forged server-owned fields reject before business writes.

## Atomic submission

The server sets owner, random UUID, a unique 64-bit random human reference prefixed
SS-, configured responsible team, null assignee, New status, standard priority,
version 1, UTC creation/update times, active archive state and no legal hold.
The unique reference index remains authoritative; a rare collision aborts without
partial state and the same form can be retried. References are display identifiers,
not access credentials. London formatting is presentation only.

One snapshot/majority transaction checks current student access, writes the actor
revocation guard and team revision, inserts case, submitted event, safe audit,
generic pending outbox job and submission-key result. No external service runs
inside the callback. Revocation/disablement and team changes serialize through the
existing guard contract. A failed audit/outbox/key write leaves no partial case.

The signed form key binds internal user UUID and 256 random bits, expires after
24 hours and carries no narrative. Only SHA-256 key and normalized-payload hashes
persist in submission_keys. Repeated same-key/same-payload POST returns the original
case; changed payload conflicts (409). Concurrent retries serialize through the
actor guard and unique key. An unknown commit result must be retried using the same
form/key, never a new form automatically. The safe 503 retains the authorised user's
text/key in the current HTML response for retry; no narrative goes into cookies,
URLs, audit data, logs, email or localStorage. An expired authenticated session
requires sign-in and a fresh form; its drafts are not persisted.

## Routing and local setup

CASE_ROUTING_JSON maps approved category names to canonical team UUIDs. Malformed,
duplicate or unknown configuration fails startup. Empty/missing routing is allowed
for public runtime checks but refuses affected submissions with a safe 503 and no
partial record. Runtime validates that the selected team is active and covers the
category. There is no silent arbitrary/default team fallback.

The explicit local configure_routing.py command maps all five synthetic teams;
existing user configuration is preserved. Three synthetic teams extend the prior
finance/disability fixtures: 30 idempotent fixture records, with unchanged 12 user
identities. Seeding uses setOnInsert and preserves existing case/account changes.
Institutional real routing/ownership policy remains unresolved. None of these
synthetic mappings is asserted to be university-approved.

All pages use the approved tokens/Jinja design system. Actual Chromium/WebKit review
covers phone/tablet/desktop overview, empty state, form, validation, confirmation,
case detail and denial. Privacy, operating hours and urgent-help wording remain
explicit approval placeholders; no response time, legal basis or monitoring promise
is invented. Stage 09 staff work, Stage 10 communication/lifecycle and Stage 11 email
remain outside Stage 08. Full accessibility certification/load testing is later work.

Implementation: app/cases/routes.py, app/services/student_cases.py,
app/repositories/student.py and app/templates/cases/. Verification:
`../evidence/stage-08/README.md`.
