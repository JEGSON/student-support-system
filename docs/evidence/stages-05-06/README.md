# Stages 05/06 — identity, sessions and access control

2 November 2026. Existing checkout; synthetic local dependencies only. Baseline
commit `703356e`. This evidence directory is committed with the implementing change;
use `git log -- docs/evidence/stages-05-06` to identify its final commit. No production
deployment, remote push, real student processing or third-party communication.

## Implemented scope

- Authlib 1.9.2 OIDC code/S256 PKCE; issuer/audience/signature/expiry/state/nonce
  checks; exact issuer/subject mapping; explicit synthetic provisioning.
- Hashed opaque Mongo sessions; anonymous attempt store; cookie flags, rotation,
  idle/absolute timeouts, CSRF, safe returns, local logout and immediate disablement.
- Explicit contexts and central deny-by-default role/relationship matrix;
  metadata-only access administration, independent privilege approval/revocation,
  offline paired synthetic bootstrap, bounded/audited triage claims.
- Real replica-set authorization guard/race check; no exposed case endpoints.

[Implementation and concurrency contract](../../architecture/identity-access-contract.md)
and [setup/run instructions](../../development/identity-access-setup.md) define exact
semantics, endpoint inventory and local HTTP exception. Architecture topology is
unchanged; the user was informed before the state-store/library/guard implementation.

## Observed checks

Initial full regression: **182 passed in 130.45 seconds**, no skips. It exercised
12 real Keycloak student/admin browser configurations plus six existing layout
configurations, signed-JWT negatives, MongoDB sessions and role/concurrency tests.
Final clean-environment regression: **190 passed in 128.61 seconds**, no skips,
recorded in `pytest-results.xml`. This includes the full HTTP request/independent-approval
workflow and the additional mapping/discovery checks. The affected identity browser
checks were repeated after the final WebKit control-height adjustment; their
result is in `browser-results.xml`: **12 passed in 18.51 seconds**.

Commands:

```sh
uv venv runtime/stages05-06-clean-env --python .venv/bin/python
uv export --frozen --format requirements-txt \
  --output-file runtime/stages05-06-requirements.txt --cache-dir runtime/uv-cache
uv pip install --python runtime/stages05-06-clean-env/bin/python --require-hashes \
  -r runtime/stages05-06-requirements.txt --cache-dir runtime/uv-cache
RUN_RUNTIME=1 RUN_BROWSER=1 \
PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers \
BROWSER_EVIDENCE_DIR=docs/evidence/stages-05-06/layout \
runtime/stages05-06-clean-env/bin/python -m pytest -q \
  --junitxml=docs/evidence/stages-05-06/pytest-results.xml
```

Python 3.14.7; MongoDB 8.0 replica set; Keycloak 26.8.1; locked Playwright 1.64.1
with Chromium 156 and WebKit 27.2. Images remain digest-pinned and loopback bound.
53 Python packages installed successfully with hashes in the clean environment.
The initial offline attempt lacked some cached wheels; the subsequent authorised
network install succeeded. `dependency-audit.json`: **53 packages, zero known
advisories** at execution time. A dependency audit is not a source-security proof.

Ruff lint/format, frozen lock, dependency consistency, foundation links/CSV/diagram
integrity and static-design checks are run separately. Machine-readable pytest
results deliberately omit request bodies, callback URLs, cookies and credentials.
Only public synthetic display labels appear in screenshots.

## Security coverage and practical limits

- **V06:** actual provider sign-in; real signed token rejection for issuer,
  audience, nonce, expired tokens, wrong signature/algorithm/missing subject;
  discovery origin/PKCE pins; wrong-state rejection before token exchange.
  Mapping rejects unknown/disabled subjects and ignores provider privilege claims.
- **V08 (current endpoints):** CSRF-protected logout/context/access operations,
  invalid field shapes and context escalation denial. Case submission/assignment/
  closure CSRF tests remain with their future features.
- **V02/V03:** 31 explicit actor/context/action relationships, disabled/revoked/
  dual-context/archive denials, approved audit scope and worker restrictions.
  No claim is made for case list/detail HTTP behaviour before those endpoints exist.
- **V04 (claim scope):** exactly five triage metadata fields; audited exclusive
  thirty-minute claim; repeat acquisition cannot extend it; expired claim denied;
  no later messages or internal notes granted. Referral/routing UI remains later.
- **V11 (current grants):** requester/target cannot approve; privileged direct
  membership grant refused; manager/audit grant/revocation; paired bootstrap
  restrictions; deactivation; real concurrent revocation rechecks before commit.
  Required-read audits, immutable audit DB privileges, outbox and full atomic
  domain effects remain Stage 07. Worker DB privilege tests remain later.

The concurrency test pauses after a real snapshot permission read, commits
membership revocation in another transaction, then resumes the mutation. The stale
write conflicts, retries, denies and leaves the case byte-for-byte unchanged.
This is real database concurrency, not a mocked denial.

## Defects discovered and corrected

The first algorithm-negative test could not generate RS512 under Joserfc's default
recommended algorithms; generation now explicitly permits that test algorithm,
while the application remains RS256-only. Keycloak required missing synthetic email
profile fields; provisioning now supplies reserved example.invalid addresses.
Overlong test case references were corrected without relaxing validators.
Fixture reset correctly refused unlabelled test sessions; test-generated sessions
now carry the synthetic fixture label, and the reset test preserves provider mapping.
A duplicate test basename blocked whole-suite collection; it was renamed. Review
found context rotation could restart absolute expiry; it now preserves the original
deadline and a regression verifies it. Failed checks were corrected and rerun.

## Render review

`browser/` contains actual student/admin account and metadata-only access screens
in Chromium/WebKit at 390/768/1440. `layout/screenshots/` preserves the runtime shell
regression. Browser tests verify no horizontal overflow and no narrative persistence
in localStorage. Visual review corrected the account selector to reuse the existing
form token styles and minimum control heights across both engines. Full manual assistive-technology and complete case UX review
remain Stage 14; automated/browser checks do not certify WCAG conformance.

## Remaining gates

Institutional identity/MFA/approval/privacy/retention/AI policy decisions remain open.
No production capacity benchmark or production readiness is claimed. Team guards
may cause contention; test the documented Stage 16 workload before capacity claims.
Stages 07 onward are unimplemented and outside this turn's Stage 05/06 authorisation.
