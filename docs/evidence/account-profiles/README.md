# Student registration and profile evidence

Post-handover feature explicitly authorised by the user. Existing local checkout,
OIDC/PKCE, current account policy, restricted web DB role and design system reused.
No Flask password database or production self-registration was introduced.

Observed focused checks: 94 unit/integration/identity/schema checks passed. Four real
registration journeys passed (Chromium/WebKit × 390/1440): reject a non-reserved
email, create a unique synthetic identity through provider registration, return to
the app, save preferred name/course, submit the first support request, deny another
student's case and admin access, then sign in again with the chosen credentials and
confirm one application principal/profile. The four edited profile screens had
zero axe violations for the selected WCAG tags. Phone/desktop screenshots were
visually inspected; this is not complete human accessibility/conformance review.

Negative/service checks cover CSRF, extra target/role fields, missing/control/long
names, empty course, HTML escaping, current active status, simultaneous/stale edits,
audit failure rollback and no profile values in audit rows. Concurrent first
logins create one student and one account-created audit; provider roles/contact/
references are ignored and disabled accounts are never recreated/reactivated.
Configuration forbids enablement on other providers/production. No new dependencies.

Browser testing initially exposed the CSP form-action restriction on a POST redirect
to the provider. The final flow uses ordinary GET OIDC initiation with prompt=create;
account creation remains behind the provider's registration form and the validated
callback. CSP was not loosened. Early failed test runs are superseded only after
correction and rerun; successful XML/results are alongside this record.

Every browser-created identity and its application records were removed using their
unique generated identifier; existing users/fixtures were preserved. Tests use the
separate test database and an owned temporary server on 5051, not the user's 5050
listener. Full regression result XML is full-results.xml. Existing Stage 16 workload
and recovery figures remain historical; signup/profile throughput was not load-tested.

Final full regression: **301 passed, zero failures/errors/skips, 192.89 seconds**.
Documentation links/XML, design checks, Ruff lint/format and private-secret comparison
passed. The updated local 5050 server was started and checked: registration is
visible, anonymous profile access redirects to sign-in and dependencies report ready.
