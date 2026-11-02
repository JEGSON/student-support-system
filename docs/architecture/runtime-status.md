# Implemented architecture and production target

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
