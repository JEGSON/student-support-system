# Student and staff portals — 4 November 2026

The unfinished redesign was resumed from its partial browser verification.
The local runner serves a student portal at `http://127.0.0.1:5050` and a staff
portal at `http://localhost:5050`, over the existing Flask/MongoDB services.
These are separate host-only cookie scopes. Requests to unknown hosts fail closed;
old `/student` and `/university` GET bookmarks redirect to their canonical portal.
Old mutations are rejected rather than forwarded or replayed.

The redesign includes the public homepage, support directory, email-first entry,
student recent-request dashboard, staff launch dashboard and responsive workspace
navigation. Seeded example cases are omitted from portal queues; their original
records remain intact. Current role, membership, case and audit checks still govern
access. A student cannot authenticate into the staff portal or select a staff
context. Staff access remains controlled through approved accounts/invitations.

Each portal has its own exact OIDC callback/client. The mounted `support-portals`
Keycloak login theme uses the provider's native fresh-account action when an
identity is remembered, before asking for a password. There is no global logout,
credential reset, cookie deletion, password handling by Flask or grant of roles.
With JavaScript disabled, the provider's manual account-selection action remains.
Issuer/signature/audience/nonce/PKCE checks remain in place. The production server
entry point is unchanged; the local runner is not a production deployment.

Observed issues and corrections:

- Sandbox service access initially produced a misleading replica-set connection
  failure. The existing containers were healthy; verification needed local service
  access outside that restriction.
- An email login hint alone did not override Keycloak's remembered identity.
  Disabling the cookie authenticator caused a different-user-session rejection;
  that trial was reverted to the standard browser flow. The portal-specific theme
  now advances through Keycloak's own account-selection control. A first theme
  draft assumed that control was a link; it is a button in the pinned provider,
  and the final script activates the native control directly.
- The browser fixture now temporarily relabels both users and teams, restoring
  their original test metadata afterwards. Screenshots use invented names, not
  private credentials. Development records/accounts are not renamed by the test.
- The first full regression exposed ambiguous duplicate navigation labels and
  removal of the provider's reserved-email restriction. Sidebar labels were made
  distinct from page actions, and local registration keeps its reserved domain
  while omitting demo-only helper copy.
- Axe checks found insufficient contrast on the homepage step numbers and mobile
  support-directory numbers. Both now use the darker green `#526a48`; the checks
  remain part of every captured portal screen.

Verification includes host routing and mutation rejection, email/CSRF boundaries,
verified callback role rejection, root-path HttpOnly portal cookies, and actual
Chromium/WebKit journeys. The browser matrix covers 390/768/1440 pixels and both
student-first and staff-first sign-in in one shared browser cookie jar. It creates
a request, assigns/starts it, sends a staff reply, verifies it for the student and
checks that student logout leaves the staff account active. Generated case records
and linked records/audits are removed by scoped teardown. Screenshots are named by
browser, width and screen; both login orders exercise the same screen captures.

Portal verification: **12 passed in 58.19 seconds**, recorded in
`browser-results.xml`. Forty-eight screenshots and matching axe reports cover
eight screens at each browser/width combination, with **zero reported violations**
for the selected WCAG A/AA tags. These automated checks do not certify accessibility.
Desktop, tablet and mobile captures were visually inspected.

The remaining regression ran separately with `--ignore=tests/browser/test_real_portals.py`
so the already-passing portal matrix was not repeated: **361 passed in 227.21 seconds**,
recorded in `regression-results.xml`. Together the two complementary runs cover
**all 373 tests, with zero failures/errors/skips on the final version**: 58 browser,
214 integration and 101 unit checks. Earlier failures are retained in
`initial-full-results.xml`, `initial-regression.txt` and `accessibility-preflight.*`.

Ruff lint/format, foundation/document links, static design and whitespace checks
pass. A scan against the actual local private values found zero matches in the
source/evidence candidates. Historical captures overwritten by legacy tests were
restored; current portal captures remain in this directory. Both running preview
hosts return 200 for the homepage, sign-in and readiness. No remote push, deployment,
real student record or external message was introduced.
