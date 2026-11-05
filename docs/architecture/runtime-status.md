# Configurable university-service runtime

4 November 2026. The current release builds on the completed local case-management
system with verified invitation enrolment, account closure/profile erasure, privacy
review, database-managed teams/intake, configured retention and opt-in production
SMTP/setup/recovery tools. No live provider/deployment is configured. Read the
[operator guide](../handbook/real-service-setup.md) for actual capabilities and gates.

The current database has **20 collection contracts**: the original 18 plus
account_closures and enrolment_invitations. Closure erases editable profile/contact
fields and closes platform sessions. Minimal HMAC suppression/attribution records
remain, linked cases follow retention review, and restored snapshots replay closure
records. This is not a claim of complete anonymisation or all-system erasure.

The local runner now uses distinct student (`127.0.0.1:5050`) and staff
(`localhost:5050`) hosts with host-only, root-path HttpOnly cookies and separate
OIDC clients. Server-side workspace binding isolates sessions, CSRF and OIDC
attempts. Legacy local GET mounts redirect; mutations must be resubmitted from a
new portal form. The general application/production entry point retains its
`/student` and `/university` compatibility mounts. Neither hosts nor URL namespaces
grant roles; current database policies remain authoritative. See the
[portal evidence](../evidence/portal-redesign/README.md) for the local provider theme
and browser checks.
Existing root URLs/sessions remain compatible. Normal sign-in requests credentials
explicitly; privileged destructive reauthentication keeps its same-person proof.

The editable eight-page architecture/PNG gallery now reflects these additions.
Core Flask/Jinja, Mongo transactions, current scope checks, separate notes, explicit
referrals and restricted worker boundaries are retained. Production web roles do
not delete cases/history/audit; approved offline maintenance handles disposal.

Single-university enrolment uses exact trusted issuer + signed verified email +
operator-issued invitation. Domain-only trust and submitted role claims grant no
access. Privileged roles still need independent approval. Destructive closure
requires same-person OIDC max_age=0/auth_time proof and explicit CSRF confirmation.

Teams/routing are administrator-managed with unique intake categories. Production
has no environment-route fallback. Retention durations, approved policy, privacy
review interval, service wording and private identity key are mandatory production
inputs. Actual host/provider credentials, service governance and external assurance
remain unconfigured. The existing loopback environment remains available for testing.

Below is the historical Stage 19 checkpoint; current details above and the operator
guide supersede its older counts/limitations.

## Historical implementation checkpoint

As-built v2, 2 November 2026. Stages 01–19 local synthetic delivery. The original
secure-design HTML remains the requirements/proposal baseline; the editable eight-
page draw.io model, PNGs and overview now identify implemented local controls and
conditional production infrastructure. No public deployment occurred.

| Area | Implemented | Remaining gate |
| --- | --- | --- |
| Application | Modular Flask/Jinja; routes → services → current policies → typed repositories | Wider role-load and large administration review |
| Identity/access | OIDC/S256, issuer+subject mapping, opaque hashed sessions, CSRF, independent grants and revocation guards | University provider/MFA and access owners |
| Case work | Own-case submission; metadata queues/expiring triage; eligible assignment; explicit start; messages/notes/corrections; question/reply; close/reopen | Institution-approved service wording |
| Referrals | Assigned source proposal → source manager approval → minimal target review → one separate New case | Real sharing grounds |
| Persistence | 18 validators/index sets; snapshot/majority transactions; version/account/team guards; atomic event/audit/outbox | Production replica topology and storage encryption |
| Worker | Restricted identity; loopback reserved-contact SMTP; leases, bounded retry/dead/expiry and age alerts; at least once | Real contact provenance, mail provider and alert routing |
| Lifecycle | Reassignment review; Closed archive; purpose-audited scoped archive read; holds; dual-approved synthetic disposal ledger/offline executor | Real retention/backup expiry and archived forensic review |
| Operations | Gunicorn template; exact trusted single proxy; shared Mongo limits; safe headers/logs; encrypted bounded snapshots and quarantined restore | Actual HTTPS edge, KMS/offsite backups, on-call and HA |

Collections: users, teams, memberships, cases, messages, internal_notes, case_events, referrals, audit_events, notification_outbox, sessions, auth_attempts, submission_keys, triage_claims, privileged_grants, service_principals, rate_limits, disposal_records. New disposal_records and rate_limits
implement the authorised retention/abuse requirements. Quarantine is a separate
operator DB; the web/worker cannot access it. No new narrative-sharing boundary.

All business mutations require current context/scope and signed CSRF; versioned
forms reject stale updates. Notes use separate service/retrieval paths. Request
identifiers and metadata-only denial audits assist review without logging bodies.
See [workflow/permission inventory](implementation-inventory.md), [evidence](../evidence/stage-16/README.md)
and [handover](../handbook/handover.md) for practical limits.

The origin URL is configured; remote history/publication was not verified. Local
Git commits supply development evidence. Earlier contracts are historical stage
checkpoints; this document and the source describe the completed local runtime.

## Post-handover account/profile extension

User-authorised synthetic student self-registration now uses the existing Keycloak
OIDC/PKCE flow. Config gates it to the exact local provider and rejects production
enablement. Staff/privileged grants remain controlled. Own profiles allow only
preferred name/optional course changes with CSRF, version/account guards and atomic
metadata auditing. Two optional users fields support profile version/time; collection
count remains 18. See [account/profile contract](account-profile-contract.md).
