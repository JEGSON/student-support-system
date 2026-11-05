# Codebase review — 4 November 2026

The user reported an invalid administrator password after the portal redesign and
requested a broader codebase review. A clean automated login alone had not explained
the user's failure. This review examined authentication/session/OIDC boundaries,
host routing, access administration and invitations, student/staff case services,
communication, referrals, retention, account closure, audit, notification delivery,
database contracts, recovery/bootstrap tools and runtime configuration. The complete
test suite, static checks and installed-dependency advisory scan provide additional
verification; they are not a claim that every possible defect has been eliminated.

## Confirmed findings and corrections

| Finding | Correction and verification |
| --- | --- |
| The local `support_web` role allowed removal of cases, messages, notes and ordinary business records, plus history updates and service-principal management. This contradicted the documented history/maintenance boundary; the production template was already stricter. | The local bootstrap now matches that separation: mutable business records have find/insert/update, messages/notes/events are append-only, audit is insert-only, and only session/auth-attempt/submission-key records retain web removal. The web role has no service-principal access. Eleven nonmatching-ID tests failed on the old grants and pass after applying the corrected roles. No records or credentials were changed by those probes. |
| Staff URLs on the student hostname used the student app/cookie. Safari still had an old staff page open there, containing obsolete sign-in links. | The host gateway redirects staff/access/retention GET/HEAD navigation to the staff host and case navigation to the student host. Cross-host mutations return 409 rather than replaying forms. New routing tests cover both directions and exact prefix boundaries. |
| The email entry/confirmation step discarded a safe `next` destination. | The confirmation and change-email links preserve the validated return path. HTTP tests follow the complete email-to-callback sequence for both portals. |
| Callback failures on the staff portal always implied staff approval was missing, including expired state and service outages. | Verified wrong-portal identities receive the appropriate portal link. Invalid/expired attempts receive a fresh-sign-in action. Database/network outages return 503. Fixed stage labels aid diagnosis without logging tokens, credentials or exception contents. Identity database failures have a safe error handler. |
| The invitation-only wording implied existing staff/administrators needed another invitation. | The sign-in page explicitly distinguishes existing staff/admin sign-in from first-time access. An invitation grants service enrolment; a matching verified identity-provider account is also required. |
| Controlled archive/audit reads validated a required purpose, then discarded it. | A bounded single-line `purpose` is stored only for these two review actions and available through the scoped audit reader. The field is optional for historical records. Development/test validators were updated without seeding or resetting records. Regression assertions verify persistence. |
| Referral acceptance checked the source snapshot without sharing the source team's concurrency guard. Concurrent archival/routing could invalidate that snapshot before acceptance committed. | Referral decisions now touch the same source-team guard used by routing/archiving. A real replica-set test commits concurrent archival after the acceptance snapshot; acceptance retries, sees the archived source, and creates no target case. Source case business fields remain unchanged by ordinary referral acceptance. |
| Notification origin checks accepted password-only or empty URL userinfo because they checked only a truthy username. | Both delivery classes reject any username/password component. Parameterised tests cover empty, password-only, username-only and username/password userinfo. |

## Login investigation

The existing saved administrator password successfully authenticated against the
running development service before this review. The new browser regression starts
with a remembered student identity, opens the old student-host staff bookmark,
authenticates the administrator, opens University invitations, and verifies the
student remains signed in. Both Chromium and WebKit pass this scenario.

The native Safari session was refreshed and inspected through the actual UI. It
now reaches `localhost:5050/sign-in` and the secure password page selects
`synthetic_administrator@example.invalid` using the `support-staff` client. No native
Safari password submission was performed in this review. The exact user-entered
password failure has not been reproduced, so the stale-page defect is not presented
as a proven explanation of that password error. Existing credentials remain unchanged.

## Verification

The first full regression passed **389 tests in 295.27 seconds** before the late
database-role finding (`before-role-tightening.xml`). After tightening the role,
all 11 new permission-denial tests pass. The complete gate under the corrected permissions passed **400 tests in 294.85
seconds**, with zero failures, errors or skips (`results.xml`): 60 browser, 230
integration and 110 unit tests. Forty-eight current portal axe reports contain
zero violations for the selected WCAG A/AA rules. Lint, formatting, foundation/link,
static-design, whitespace and actual-secret checks pass. Historical screenshots
overwritten by legacy tests were restored. The local preview was restarted with
the corrected source; both host readiness checks pass.
Portal captures and axe outputs are kept under `portals/`; older evidence remains
historical. `dependency-audit.json` reports **55 installed Python dependencies,
zero skipped entries and zero known advisories** at the time of this review.

Seven new routing/URL tests failed against the pre-fix code (`initial-unit.txt`).
All 11 new permission probes failed on the previous grants (`initial-roles.txt`).
The first concurrency fixture introduced an artificial nested user-lock conflict;
that failed attempt is retained in `initial-focused.txt`. The corrected regression
models the independent case/team archival writes and passes on the real replica set.
There was no change to transaction timeouts to accommodate that test.

The additive audit validator is installed with the existing offline schema command.
Production operators must apply the current schema through their existing explicit
maintenance workflow before running this source; no production service was accessed.
