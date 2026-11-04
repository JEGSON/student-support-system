# Parallel student/staff accounts — 4 November 2026

User-reported defect: after student login, another tab's sign-in reused that
account instead of allowing concurrent university staff access. Existing app
cookies were shared between tabs, and provider SSO could reuse the last identity.

Implemented two fixed mounts (`/student`, `/university`) using the same Flask
application, services and MongoDB. Each uses a distinct path-scoped opaque HttpOnly
cookie. Stored authenticated and pending-OAuth sessions are bound to that workspace;
copying a token into the other namespace fails closed without revoking its original
session. CSRF, redirects, static assets, callback and fresh-authentication paths
stay inside the current mount. Root URLs/legacy sessions remain compatible.
Namespaces are not roles: current memberships/grants still determine all access.

Account pages provide separate-account links; staff entry prominently offers the
separate staff workspace. Normal sign-in requests `prompt=login`. The local
provider can display a remembered username; choose its “Not you?” reset control
to enter the other identity. Reauthentication for deletion remains prompt=login,
max_age=0 plus same-principal/auth_time validation. No global provider logout is
used, so one app-workspace logout does not invalidate the other principal.

Only exact loopback root/student/university callback URLs were appended to the
existing local/test OIDC clients. No wildcard URLs, reset accounts, role grants or
production provider changes were made. The operator guide specifies the exact
callbacks required when real services are connected.

Verification:

- Four actual browser flows: Chromium/WebKit × student-first/staff-first. Two tabs
  share **one browser context/cookie jar**. Login both; refresh and assert distinct
  names and cookie paths; student submits; manager assigns/starts/replies; student
  sees reply; cross-workspace CSRF is refused; student logout leaves staff active.
- Two actual different-browser flows swap Chromium/WebKit between student and
  staff, including legacy unprefixed account URLs.
- Three HTTP boundary checks: copied tokens rejected in the other workspace;
  root cookies not inherited; namespace grants no staff/admin role; exact prefixed
  callback, safe return and same-account destructive reauthentication paths.
- Existing unit/session/account checks retained. No private credentials appear in
  screenshots. Generated requests and their linked records/audits use scoped test
  teardown. Existing development records were preserved.

Observed test corrections: local Keycloak's remembered-username screen needed its
reset-login control before filling another username. An initial name assertion
used the wrong word order for the synthetic manager; corrected to actual fixture
metadata. A pre-existing exact session-data assertion was updated for the new
workspace marker. These were not hidden or relabelled as passing results.

This prevents accidental session collisions; it does not create separate security
origins against an already compromised application/browser. Tabs within one
workspace intentionally share that account. Account closure/deactivation still
revokes all sessions belonging to that principal as designed.

Final observed result: **349 passed, zero failures/errors/skips in 223.51 seconds**
(full-results.xml): 46 browser, 208 integration and 95 unit tests. Focused preflight
runs also passed six real browser tests and 21 identity/account/workspace tests.
The updated main app returned 200 for readiness, both workspace landing pages,
prefixed CSS and staff entry. Native Safari loaded `/university/staff/sign-in`
without inheriting the existing root account, while the user's original tabs
remained untouched. Architecture view 06 was rendered and visually reviewed;
Ruff, formatting, foundation/links and whitespace checks passed. A source/evidence
scan found zero matches against 32 private comparison values.
