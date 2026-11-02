# Development progress

- Created directory and documentation scaffold.
- Copied existing architecture and prompt artefacts where available.
- No application features, dependency environment or automated tests exist yet.

## 2 November 2026 — Prompt 01

Completed repository planning: provenance-labelled requirements, FR/SR/BR/WF/T/V
traceability, ADR extraction, OD owners and gates, prioritised Prompt 02–19 backlog,
delivery definition, toolchain proposal and honest evidence/AI records. Restored
the eight baseline PNG previews so the architecture gallery is self-contained.
See `../evidence/stage-01.md` for actual checks and limitations.

Application code and runtime remain absent. No GitHub remote, push or deployment.
Missing rubric, attachment, deadline, AI policy and institutional approvals remain
open; they do not block synthetic planning/design. FR-04/06 definitions are unknown.

Next: Prompt 02 visual design and UX specification, on separate user instruction.

## 2 November 2026 — sequential delivery authorisation and Prompt 02

The user instructed following the prompt file one by one to build the website,
with progress updates. This authorises continuing local stages sequentially without
repeating stage permission questions. Remote push, production deployment, real
student information and contacting third parties remain excluded. Required stage
gates still apply; do not advance over unresolved required verification.

Stage 02: documented tokens, information architecture, seven annotated layouts,
responsive rules, component/state inventory and eight isolated static prototype
pages. Static checks pass. Browser host unavailable/native Chrome timed out;
rendered visual review limitation recorded in `../evidence/stage-02.md`. No actual
application permissions/authentication are implemented in the design prototype.

Next: Stage 03 runtime, including its stricter verification requirements.

## 2 November 2026 — Prompt 03 runtime checkpoint

Flask factory/configuration/health, Jinja design system and development-only
component/student/staff shells implemented. Generated ignored local secrets;
started authenticated MongoDB replica set, isolated Keycloak realm and Mailpit
with digest-pinned Compose images. Separate development/test database credentials
verified. Locked dependencies installed in the preserved existing environment.
Final runtime suite: 17 passed, including a real aborted transaction and mutual
cross-database read denial. Setup/readiness failures and fixes are recorded in
`../evidence/stage-03.md`, including occupied ports and identity/bootstrap issues.

Stage 03 is INCOMPLETE: native browser access was intermittent; required responsive
render/focus/reduced-motion review at 390/768/1440 has not completed. The user is
working on browser access; latest browser-host inventory still reports unavailable.
Do not claim Stage 03 complete or start Stage 04 until that gate is resolved.
Local preview runs on 127.0.0.1:5050. No case management, login/session features,
real student information, remote push or deployment have been introduced.

## 2 November 2026 — Safari access retry

The user requested checking access again or using Safari. Safari opened the actual
local site and desktop rendering was inspected. Responsive developer controls
remained blocked by repeated native timeouts; the browser connector also remained
unavailable. The user approved temporarily enabling developer features, but the
attempt timed out and the checkbox state/restoration could not be verified (original
OFF). See `../evidence/stage-03-safari-access.md`. Stage 03 remains incomplete.
An origin URL is now configured locally by an external/user action; no remote
history was verified and no fetch/push was performed in this turn.

## 2 November 2026 — Stage 03 redo complete

Reread all architecture artefacts and Stage 03 requirements. Preserved the modular
Flask/Jinja/MongoDB design. Tightened local database destination and OIDC readiness
validation. Verified a clean runtime-only hash-checked install. User explicitly
approved Playwright; isolated Chromium/WebKit at 390/768/1440 now verify four actual
runtime pages and save 30 screenshots. Fixed tablet action shrink/wrapping after
visual review. Final suite: 29 passed in 77.89s. Stage 03 COMPLETE; full V14/V16
remain partial for their later-stage scope. Safari developer setting restored OFF
and verified. See `../evidence/stage-03-recheck/README.md`.

Next: Stage 04 validators, indexes, repositories and controlled synthetic fixtures.

## 2 November 2026 — Stage 04 complete

Installed/tested 15 collection contracts and explicit indexes on the actual replica
set. Added typed repositories/reference integrity, UUID/UTC/London helpers, a
separate schema setup identity and 27 idempotent synthetic records. Fixtures cover
the required actor/team relationships without usable login credentials. Safe reset
preserves unlabelled data and rejects dependent records. Runtime suite: 79 passed,
six unchanged browser configurations skipped; prior Stage 03 browser evidence remains.
Documented schema additions, migration limits, fixture setup/reset and actual failed/
corrected test expectation. See `../evidence/stage-04.md`. No case-management routes.
Next: Stage 05 OIDC and opaque server-side sessions; no local-password substitute.
