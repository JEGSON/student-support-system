# Identity and access implementation — Stages 05/06

Historical stage checkpoint. For the completed local runtime and current additions,
see [as-built status](runtime-status.md) and [inventory](implementation-inventory.md).

2 November 2026. Read alongside the preserved v1.0 design HTML and eight-page
editable draw.io baseline. This implements ADR-04/05 and the existing relationship
rules. No trust boundary or product scope change is introduced. The user was
informed before implementing the additive short-lived OIDC-state store. Operational
hardening, business transactions and case pages retain their numbered stage gates.

## Identity boundary

Authlib 1.9.2 implements authorisation code with S256 PKCE, state and nonce. Discovery
must report the exact configured issuer and S256; authorisation, token and JWKS
endpoints must have the issuer's origin. RS256 is explicitly allowed; arbitrary
JWT algorithm headers cannot broaden it. Issuer, audience, signature, essential
claims, expiry and nonce are validated before account lookup. Accounts are looked
up by verified issuer/subject and active status. Provider role/group/profile claims
never provision an account or assign roles. No app password login/self-registration.

Same-origin discovery endpoints are a deliberate fail-closed local engineering
constraint; an institutional provider with different endpoint origins will need a
reviewed explicit allowlist before integration. Production requires HTTPS, reviewed
`OIDC_REQUIRED_ACR` and an explicitly configured client authentication method/secret.
The exact institutional authentication class and staff MFA policy remain unresolved.
The development public client has no client secret; it requires PKCE. No insecure
OAuth environment override or production HTTP exception is enabled.

## Browser and server sessions

`support_session` contains only 256 random bits encoded as 43 URL-safe characters.
Only its SHA-256 hash is stored/indexed. Session data are server-owned context,
CSRF token and (anonymous only) Authlib state/nonce/verifier/redirect metadata.
Access/refresh/ID tokens are used for the exchange and discarded, never persisted
in the cookie, localStorage or logs. Authlib state is in the additive `auth_attempts`
collection, indexed by token hash with TTL cleanup at absolute expiry. This is the
16th strict collection contract, not business/student content storage.

Anonymous attempts expire in ten minutes. Authenticated sessions have an eight-hour
absolute deadline and 30-minute student / 20-minute other-context idle limit.
Context switches rotate tokens while preserving the absolute deadline and original
authentication timestamp. Successful login rotates the anonymous token. Logout
revokes the current token, clears the cookie and requires CSRF-protected POST.
TTL is cleanup only: every request checks idle/absolute expiry and active account
status. CAS versioning stops stale session saves from restoring revoked data.
Disablement/revision changes through AccessService revoke existing sessions.

Cookies are HttpOnly, SameSite=Lax and Secure in production. Only explicit
loopback HTTP development/testing omits Secure. Forms have global Flask-WTF CSRF;
expired forms return a safe restart message without echoing submitted content.
Return paths allow only `/account` and `/access`. The local runner logs method and
status, omitting URLs, queries, callback codes, bodies and exception contents.
Local logout does **not** terminate the university/Keycloak SSO session. A subsequent
sign-in may complete via SSO; shared-device users need the provider's sign-out flow.
RP-initiated/back-channel provider logout is not implemented or claimed.

## Authoritative relationship policy

All case/business routes are still absent. `Policy` reads active internal accounts
and current memberships; unknown actions/contexts and archived routine cases deny.
Explicit student/staff/admin/audit contexts prevent combining dual-role privileges.
Students read only their own cases/messages. Officers need both current assignment
and active membership in an active team. Managers have team-scoped access. Only
managers can assign/reopen/approve referrals. Students never read internal notes.
Administrators manage account metadata, never routine narratives. Approvers can
approve grants, not administer accounts by default. Audit reviewers need an approved
team-scoped grant plus a bounded purpose; audit permission does not grant narratives.
Workers have only a narrow notification action allowlist and no interactive login.
Actual scoped worker database credentials are a later stage requirement.

Triage queues use exactly reference/category/created_at/status/team_id. Claims are
exclusive, audited and last at most 30 minutes; repeat acquisition never extends
expiry. Every initial-request decision checks current membership, account revision,
team, owner, New status and times. Later messages/notes remain denied. Routing,
release UI and safe narrative views arrive with Stage 09 after audited-read support.

## Privileged changes and concurrency

`/access` is authenticated, CSRF protected, context restricted and metadata only.
All changes delegate to `AccessService`; crafted fields, duplicate form keys,
unknown operations and direct manager grants deny. Ordinary officer/triage membership
is administered explicitly. Manager/admin/approver/audit grants need a pending request
and a separate active approver who is neither requester nor target. Approval and
role/membership changes, revision increments, session revocation and metadata audit
commit together in a MongoDB transaction. Privileged revocation/deactivation preserve
history. Accounts cannot disable/revoke their own administrative access through
these operations. Required staff-departure reassignment reporting remains Stage 13.

`bootstrap_access.py` is an offline local synthetic-only paired bootstrap, requiring
explicit distinct, active, mapped, unprivileged fixture accounts and a reason. It
writes two independently attributed approved grant records and audit events in one
transaction. Repeat/bootstrap-to-self/unmapped/disabled/production targets refuse.
Local fixture seeding is already an explicit trusted synthetic setup; generated
provider passwords are unique, private and never committed. This tooling is not an
institutional production bootstrap approval process.

`guard` reads policy/case inside a snapshot transaction and writes the actor guard,
team revision and case version before the mutation callback. Membership revocation,
privileged change and disablement write the same actor revision/guard. If revocation
commits first, a stale mutation conflicts, retries and denies; if the mutation
commits first it precedes the revocation. There is no promise to cancel work already
committed before revocation. Assignment/team conflicts must likewise use guarded
transactions; direct repository/DB writes outside these services bypass the contract.
PyMongo retries labelled transient failures/uncertain commits under a five-second
client operation deadline. Callbacks contain database work only. Generic case
history/outbox/idempotency and protected audit-before-read remain Stage 07.

Writing the team guard serialises overlapping team mutations and may create a
contention point. This is a correctness-first proposal, not a demonstrated capacity
claim. Stage 16 must measure it and any optimisation must retain revocation semantics.
Session lookups use unique token indexes. Access lists are bounded to 100 records;
search/keyset administration pagination needs extending before large deployments.

## Sources consulted

- [Authlib Flask integration](https://docs.authlib.org/en/latest/oauth2/client/web/flask.html)
- [Authlib HTTP clients](https://docs.authlib.org/en/stable/oauth2/client/http/index.html)
- [Flask-WTF global CSRF](https://flask-wtf.readthedocs.io/en/1.2.x/csrf/)
- [PyMongo transactions and retry callbacks](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/transactions/)
- [Keycloak administration REST API](https://www.keycloak.org/docs-api/latest/rest-api/index.html)

Installed Authlib/Joserfc implementation was inspected alongside current primary
sources. Evidence and remaining limits: `../evidence/stages-05-06/README.md`.
