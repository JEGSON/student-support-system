# Stage 08 student case journey evidence

2 November 2026. Stage 07 prerequisite commit: 7f6b3e5. Local-only synthetic
implementation, no remote push/deployment, real student information or external email.

Implemented own-case overview, accessible request form, confirmation and case detail;
scoped repository projections; explicit five-category routing; atomic case/event/
audit/outbox/key persistence; safe idempotent retry; read-audit-before-response.
[Exact contract](../../architecture/student-journey-contract.md) and
[setup](../../development/student-journey-setup.md).

Observed intermediate checks: 64 unit tests and 144 actual-Mongo integration tests
passed. Real Keycloak student journey: six Chromium/WebKit configurations at
390/768/1440 passed in 14.88s before the final readability/repository refinements.
Final complete result: **236 passed in 144.49s**, no failures/errors/skips, in
`pytest-results.xml`. This includes the CRLF, Unicode-body-bound, runner-secret and
condition-based browser regressions. **84 synthetic screenshots** cover current
student/identity/layout scenes across Chromium/WebKit at all three widths.

The complete run uses the prior clean hash-checked 53-package environment; no new
package installation was required. Itsdangerous 2.2.0, already a locked Flask
dependency, is now explicitly declared because application code uses it directly.

```sh
RUN_RUNTIME=1 RUN_BROWSER=1 \
PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers \
STUDENT_EVIDENCE_DIR=docs/evidence/stage-08/browser \
IDENTITY_EVIDENCE_DIR=docs/evidence/stage-08/identity \
BROWSER_EVIDENCE_DIR=docs/evidence/stage-08/layout \
runtime/stages05-06-clean-env/bin/python -m pytest -q \
  --junitxml=docs/evidence/stage-08/pytest-results.xml
```

Coverage: V01 student submit/list/detail; V02 foreign/missing/malformed/archive
uniform denial and signed pagination isolation; V07 forged owner/team/status/role,
JSON/operators/duplicate fields/length/control checks and inert scripts; V08 CSRF,
user-bound/forged submission keys; V10 lost-response replay, changed-payload conflict,
real concurrent same-key submission, rollback after case/event/audit and before
outbox/key. V11 read-audit failure returns no sensitive content. All previous stage
checks run alongside these. Later staff/message/referral/retention/operational
coverage remains explicitly pending.

Browser scenarios include real OIDC sign-in, empty state, server validation error,
form, confirmation, overview, repeated same-key POST and another student's 404.
Screenshots contain labelled synthetic text, including inert script-like text as
security evidence. Browser contexts use no personal profiles, no localStorage
narratives and only loopback dependencies. Student test data are explicitly cleaned
and original test fixture archive flags restored. Historical screenshots are not
overwritten: each suite's evidence destination is configurable/restricted.

Discovered/corrected failures: old tests expected 404 before case routes existed;
they now require authentication redirects. The first browser retry exposed CRLF/LF
payload differences, fixed by normalization before validation/storage/hash with a
regression. A missed helper import was caught and corrected before the successful
rerun. A runtime invocation inside the network sandbox could not reach the replica
set; it was stopped and rerun with authorised local network access. That is a
verification-environment failure, not represented as an application pass. A later
WebKit rerun caught an immediate visibility assertion racing document rendering;
the test now uses condition-based Playwright expectations, without fixed sleeps or
auto-retries that mask application failures. Final validation includes the runner
secret allowlist and Unicode form limit regressions.

Full manual assistive-technology and institutional policy approval remain Stage 14/
open decisions. This is not WCAG certification, production capacity or readiness.

Final checks: Ruff lint/format, compile, frozen lock, dependency consistency,
foundation/diagram/link and static design checks passed. Advisory report:
**53 packages, zero known findings** (`dependency-audit.json`). All prospective
tracked files were compared to private generated secrets; no matches found.
Credentials and environments remain ignored; the credential file is mode 0600.
This evidence is committed with Stage 08; use `git log -- docs/evidence/stage-08`
to identify its implementation commit.
