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
