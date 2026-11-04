# Function and browser walkthrough — 4 November 2026

The user requested loading the website and testing its functions/classes one by
one, showing the actions and results. Existing checkout, development data and
local Flask/MongoDB/OIDC architecture were retained. No deployment, remote push,
real student information or external email was involved.

## What was shown and tested

Safari was opened to the running localhost:5050 app. The homepage, student
registration guide, privacy page, staff entrance and actual local OIDC sign-in
page loaded through their normal links. The normal readiness endpoint returned
200/ready. The browser connector remained unavailable; native Safari access worked.

Mutating tests used the existing isolated test database and disposable browser
contexts. The desktop Chromium complete journey was also launched visibly with
slowed interactions. Screenshots provide persistent, inspectable evidence:

| Area | Actions and assertions |
| --- | --- |
| Identity | Actual local Keycloak code/PKCE sign-in, context, opaque cookie, logout and disallowed return URL. |
| Registration/profile | Synthetic provider signup, invalid-address handling, own-profile edits and persistence, first request and forbidden admin/other-student access. |
| Account closure | Same-user fresh authentication, explicit closure, erased editable fields, revoked sessions, preserved linked case and blocked automatic re-enrolment. |
| Student requests | Submit, view, pagination, escaped text, duplicate-submit replay and ownership denial. |
| Staff work | Scoped queue, assignment, start, question, private note, student reply, closure, stale form and expired session. |
| Referrals | Deliberate summary, source approval, target-only summary, acceptance into a separate case and isolation of source narratives/notes. |
| Enrolment/teams | Create team/intake route, show-once invitation, verified email/issuer binding, ordinary staff access and forbidden privileged self-enrolment. |
| Triage/archive | Claim/read/release, revoked claim access, reassignment review, version-checked archive and purpose-audited scoped archive read. |
| Privacy/retention | Admin closure review, invalid review interval, retained-record decision, retention metadata and independent disposal controls. |
| Worker/recovery | Generic local email, retry/dead/overdue state, worker restrictions, verified TLS ordering with substitutes, encrypted quarantine and closure/disposal replay. |
| Browser/accessibility | Chromium/WebKit at 390/768/1440, keyboard/focus/reflow, selected axe rules, no forbidden remote gallery requests. Human accessibility review remains separate. |

The interactive [report](index.html) lists every test result, every named runtime
Python function and every declared class, with links from an observed function to
the tests during which it ran. Raw data is in function-review.json and full-results.xml.

## Corrections and evidence limits

The first run had 334 passes and one fixture-reset failure. Its XML/progress are
retained as initial-full-results.xml and initial-test-progress.jsonl. The safeguard
correctly refused to remove fixtures referenced by another audit record. Metadata
and test timing identified a single denial audit during the visible Chromium test.
Native browser auxiliary requests can fall outside page response listeners. Test
cleanup now collects request IDs from all requests handled by its isolated server,
then removes only audit records matching that test's IDs. The exact already-created
record was removed by its UUID, request UUID, actor, action and outcome. No broad
actor deletion or relaxed reset guard was used.

The first instrumentation cache also used Python code-object equality, which can
merge identical constructor bytecode across classes. Its initial-function-review.json
is retained for diagnosis and must not be used for final coverage counts. The final
instrumentation uses object identity and keeps code objects alive in its cache.
One new-test draft incorrectly passed an invitation record where its UUID was
required; corrected before the final run. The five additional HTTP/alert tests
then passed. These were test/instrumentation corrections; application logic was
not changed by this review.

Observed execution is not line/branch coverage or proof that every internal helper
has a dedicated assertion. Only named Python functions under app/ and worker/ are
inventoried; lambdas, dependencies and standalone script functions are excluded.
Subprocess CLI execution and the separate localhost:5050 process are not traced.
Public Safari checks are recorded separately above. Production SSO/SMTP/hosting,
real capacity, full human accessibility and all possible failure branches remain
outside this local run. Synthetic test records are removed by their scoped teardown.

## Reproduction

The exact instrumented runner and report builder are saved as text alongside the
results. They contain no credentials. For a fresh reproduction, copy them into
runtime/function-review/run_review.py and runtime/function-review/build_report.py
respectively (the runner derives the repository root from that location), choose
a new evidence output directory in both scripts and retain prior outputs. With
the existing dependencies/identity fixtures running:

```sh
.venv/bin/python runtime/function-review/run_review.py
.venv/bin/python runtime/function-review/build_report.py
```

To run the expanded checks without call instrumentation or visible slow motion:

```sh
RUN_RUNTIME=1 RUN_BROWSER=1 \
PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers \
.venv/bin/pytest -v
```

Browser tests need the documented development-only axe-core installation. These
commands intentionally perform test-only mutations, including synthetic profile
closure/disposal and teardown. They never enable a production provider or mail.

## Final observed results

- **340 passed**, zero failures/errors/skips, 232.14 seconds in the final full run.
- **260 / 260 named app/worker functions observed executing**; 31 declared classes inventoried. Each function maps to its exercising test cases.
- Five new HTTP/operational regression checks passed before inclusion in the final suite.
- Earlier failed reset/instrumentation evidence remains labelled separately.
- Native Safari/public checks plus isolated Chromium/WebKit journeys and scoped axe checks completed; this does not establish exhaustive branch, production-provider or human accessibility coverage.

Final breakdown: 40 browser tests, 205 integration tests and 95 unit tests. Native
Safari also rendered the report itself: screenshots loaded, searching for
AccountPrivacy.close filtered the inventory, and expanding that method displayed
its eight exercising browser/integration cases. The report preview was temporary;
index.html and its relative assets are retained for reopening locally.

Ruff and whitespace checks passed. The report's local links/assets were checked,
foundation integrity passed, and the source/evidence secret scan found zero
matches against 32 actual private comparison values. These checks make no claim
about arbitrary unknown secrets or production acceptance.
