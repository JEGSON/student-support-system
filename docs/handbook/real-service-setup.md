# Configurable university service: operator guide

3 November 2026. This release keeps the existing Flask/MongoDB/OIDC architecture.
It implements account closure/profile erasure, verified university invitations,
team/routing administration, policy-driven case disposal and opt-in TLS email.
It does not create hosting, a domain, provider accounts or institutional policies.

## Try the new features locally

The existing development installation and data are preserved. After updating:

```sh
.venv/bin/python scripts/configure_account_keys.py
.venv/bin/python scripts/start_dependencies.py
.venv/bin/python scripts/database_setup.py --environment development
.venv/bin/python scripts/database_setup.py --environment testing
.venv/bin/python scripts/run_local.py
```

Stop an existing project runner in its own terminal before starting another 5050
listener. The account-key command preserves an existing key and records the prior
local key when introducing a separate one; it never prints secrets. First-time
setup still uses setup_local.py and the existing provisioning/routing instructions.

- Profile → **Delete profile and close account** → sign in again → type DELETE.
  Preferred name/course/reference/contact are removed; sessions end, pending mail
  is stopped and a closure reference is displayed. Linked support cases remain
  available for authorised retention review. The university-wide identity is not
  deleted. Staff must first transfer/revoke their memberships/privileges.
- Administrator → Manage service access → **Support teams and routing**. Create
  teams, choose coverage and assign each intake category to one responsible team.
  A team/category cannot be removed while it would invalidate existing cases.
- Administrator → **University invitations**. Choose the intended email and initial
  student/officer/triage role; select a team for team roles. The 24-hour code is
  shown once. Share it over the approved secure channel; the app does not currently
  email invitation codes automatically. Revoke/reissue if it is lost.
- Invitee → **Join Student Support** (`/join`) → code → university sign-in. The
  signed email_verified claim must be true and the address/issuer must match.
  A verified email alone without an invitation is insufficient for new production
  enrolment. Existing accounts do not gain new roles from an old invitation; use
  normal access administration for membership changes. Manager/admin/approver/audit
  access continues to require independent approval.
- Administrator → **Account privacy requests** records policy-based retention
  explanations and a review deadline. It does not pretend profile closure has erased
  every case. Case disposal remains separately requested, independently approved and
  executed offline. Minimal closure/security metadata is still personal data and
  requires an approved retention/review procedure.

Local Keycloak remains a separate synthetic test identity environment. To test
invitations locally, use approved synthetic identities with verified email; do not
mark real addresses verified without proof. The real-browser invitation tests use
unique synthetic provider identities and remove them afterwards. New production
users are never seeded from local demo fixtures.

## Student and staff accounts at the same time

Open `/student/sign-in` for the student identity and `/university/sign-in` for
staff/admin in another tab. The account page provides **Open student account
separately** and **Open staff account separately** links. Each workspace retains
its own opaque session cookie, CSRF values, OAuth state and expiry. Refreshing or
signing out of one does not replace the other account. Tabs within the same
workspace share that identity. Existing unprefixed URLs remain compatible.

Sign-in explicitly requests credentials. If the identity provider displays its
previous username, choose its **Not you?** / restart-sign-in control before entering
the other username. Local application logout does not end every identity-provider
session. Separate browsers/profiles keep separate cookie jars as usual.

For an existing local install, configure the exact additional loopback callbacks
without resetting data/accounts, then restart the app:

```sh
.venv/bin/python -m scripts.configure_workspaces
```

## Production configuration

Use the three templates under infrastructure/production. They contain placeholders,
not operational credentials. Put actual configuration in protected files outside
Git or in the university secret store, with separate process access:

- web.env.example: restricted web DB identity, OIDC client, stable identity key,
  institution branding, approved service/privacy text and actual retention policy.
- worker.env.example: restricted worker DB identity and SMTP credentials only.
- operator.env.example: privileged offline schema/bootstrap/disposal/backup/restore
  connections; never mount these in web/worker processes.

All real connections require verified TLS. Configure the exact public HTTPS origin,
allowed host, private backend and one explicitly trusted proxy peer. Do not expose
Flask's development runner or MongoDB publicly. Run Gunicorn using gunicorn.conf.py
behind the approved HTTPS edge. Example with privately supplied configuration:

```sh
uv sync --frozen --no-dev
uv run --no-sync --env-file /secure/web.env gunicorn -c gunicorn.conf.py wsgi:application
uv run --no-sync --env-file /secure/web.env python scripts/check_production.py --configuration-only
uv run --no-sync --env-file /secure/web.env python scripts/check_production.py
```

A valid configuration is not proof of legal approval, accessibility or security.
The checks report missing intake routes/bootstrap and notification/closure counts;
they never return names, case text or secrets. All five category retention values,
a policy reference, privacy review interval, provider requirements and actual
service wording are mandatory for production. No real retention duration is supplied
by the code. A student reference beginning SSU is an application reference, not an
assertion of an official university student ID; trusted student-record integration
is still a separate task.

Register these exact redirect paths on the same configured HTTPS origin: `/auth/callback`,
`/student/auth/callback` and `/university/auth/callback`. Do not use wildcard callback
URLs. Verify the provider’s credential prompt/account-switch control during integration.

The identity provider must validate ownership of the intended email before issuing
email_verified=true, support the approved authentication class/MFA and fresh
max_age=0 authentication with auth_time for destructive operations. Configure its
verified email-change and password recovery flows. OIDC_ACCOUNT_URL may point to
an approved account-management page on that provider's origin. The app refreshes a
verified contact from signed claims at sign-in and audits contact changes without
storing the address in audits. No password/reset endpoint or IdP administrator
credential is exposed by Flask.

For a university SSO provider, /join creates the application profile on the first
approved login. If the university operates its own Keycloak identity realm, set up
that production realm, persistent identity DB, verified email/reset delivery and
MFA separately. Its registration/recovery UI handles credentials. The local
configure_registration.py command is never used against production.

## Initial database and operator setup

A DBA prepares a separate production replica set and role assignments. The
mongo-roles.js template defines web, worker, audit-reader and maintenance roles;
run it only in an approved DBA context with its administrative URI injected through
environment/secret storage, not command-line arguments. The template does not make
users or rotate existing passwords. A DBA must assign the roles to the matching
runtime users and separately arrange read-only backup, schema and quarantine access.
Syntax was checked locally; no production database was contacted for this release.

The operator then installs contracts and bootstraps two independently verified
university identities. Supply subject/name/verified_contact JSON on protected stdin,
not as shell arguments. The bootstrap refuses existing privileged enrolment and
serialises competing attempts with a disabled bootstrap guard. It returns only
internal account IDs and the notification principal ID. The two identities are
operator-attested; the command does not establish university eligibility itself.

```sh
uv run --no-sync --env-file /secure/web.env --env-file /secure/operator.env \
  python scripts/production_setup.py schema --ack-production-maintenance
uv run --no-sync --env-file /secure/web.env --env-file /secure/operator.env \
  python scripts/production_setup.py bootstrap --ack-production-maintenance
```

The stdin document has this shape; replace every placeholder using independently
verified provider metadata and keep the completed document out of source control:

```json
{
  "administrator": {"subject": "REPLACE_WITH_VERIFIED_SUBJECT", "name": "REPLACE_WITH_NAME", "verified_contact": "REPLACE_WITH_VERIFIED_ADDRESS"},
  "approver": {"subject": "REPLACE_WITH_OTHER_SUBJECT", "name": "REPLACE_WITH_OTHER_NAME", "verified_contact": "REPLACE_WITH_OTHER_VERIFIED_ADDRESS"}
}
```

After entering the protected JSON on stdin, sign in as the administrator and
configure teams/routes, invite staff and request privileged grants for independent
approval. Production intake uses database-managed routes; the old environment JSON
fallback exists only for local compatibility. One administrator is not automatically
entitled to every case; team manager/officer scope still controls narratives.

## Email delivery

Choose the university-approved sender domain/provider and complete its sender/DNS
verification. Set SMTP credentials and ssl or starttls; certificate/hostname checks
cannot be disabled. Only then explicitly set EMAIL_DELIVERY_ENABLED=1 in the private
worker configuration and run:

```sh
uv run --no-sync --env-file /secure/worker.env python scripts/run_production_worker.py
```

Use --once for a one-job check. No real SMTP connection or external email was made
while building/testing this release. TLS/authentication/message behaviour was tested
with controlled substitutes; local Mailpit capture remains the integration target.
Case emails stay generic, without categories, diagnoses, note bodies or tokens in
URLs. The worker reads current account state and verified contact, retries bounded
failures and records dead/overdue counts. Monitor those counts and process liveness
with an approved alert destination. Delivery is at least once, and an already
in-flight email cannot be recalled by account closure. Bounce/webhook ingestion,
automatic invitation email and provider-specific alert routing are not implemented.

## Disposal, identity keys and recovery

Real case disposal requires the configured category durations/policy reference,
Closed+archived state, no hold, a requester and independent approver who still have
access. Execute only a selected approved record:

```sh
uv run --no-sync --env-file /secure/web.env --env-file /secure/operator.env \
  python scripts/production_setup.py dispose --record RECORD_UUID --ack-production-maintenance
```

Profile closure erases its editable fields but does not delete every narrative,
security record or closure fingerprint. Review linked records and complete the
appropriate disposal/privacy process. The protected stable identity key prevents
silent re-enrolment of a closed identity without keeping its raw issuer/subject.
Retain the relevant previous keys when rotating it; do not silently drop an alias
needed for existing closure records. Key/closure-metadata expiry and any deliberate
re-registration require a reviewed institutional procedure. The current product
has no automatic complete-data-erasure/fingerprint-expiry or account-reactivation
button; it reports profile erasure and retained-record review honestly.

Encrypted backup/ledger commands now support explicit production source snapshots
and offline quarantine rehearsals. Keys must be 0600 and outside the backup directory.
Snapshots are capped at 200 MiB expanded JSON and use bounded in-memory processing;
this pilot tool is not a large-scale backup system. Choose an approved managed/
streaming backup strategy before exceeding that bound. Arrange independent offsite
custody and an approved expiry schedule; replication alone is not a backup.

```sh
uv run --no-sync --env-file /secure/web.env --env-file /secure/operator.env \
  python scripts/production_recovery.py backup --file snapshot.enc --ack-production-maintenance
uv run --no-sync --env-file /secure/web.env --env-file /secure/operator.env \
  python scripts/production_recovery.py ledger --file latest-ledger.enc --ack-production-maintenance
uv run --no-sync --env-file /secure/web.env --env-file /secure/operator.env \
  python scripts/production_recovery.py restore --file snapshot.enc --ledger latest-ledger.enc \
  --quarantine student_support_restore_rehearsal --ack-latest-ledger --ack-production-maintenance
```

Restore requires an empty dedicated quarantine, applies the latest case-disposal and
account-closure ledger, clears sessions, revokes restored invitation codes and stops
stale mail. The production app refuses quarantine DB names. A partial restore stays
offline. The operator must verify ledger freshness, secrets, permissions and integrity
before any separately controlled live activation; no automatic activation is provided.

## Launch gate and remaining inputs

Before accepting personal records: supply actual domains/provider registrations,
hosting/DB/SMTP accounts and credentials; name administrators/independent approvers,
support/privacy/security/on-call owners; approve purposes, lawful basis/special-
category condition, retention and service/urgent-help procedures; assess/complete
DPIA where required; review processors/locations/transfers and backup custody;
complete independent security/human accessibility tests and a controlled real-user
pilot. Existing local workload measurements do not certify the new full release's
production capacity. These are deployment/operating inputs, not invented approvals.
