# Endpoint, permissions and workflow inventory

As-built local v2. All POST requests require CSRF; services validate current actor/context,
scope and input independently. GET/HEAD do not change business state (session/read-audit
metadata may change). Health and authentication routes have their specific public rules.

| Methods | Route | Current authorisation/data boundary |
| --- | --- | --- |
| GET | `/` | Public landing; no case content. |
| GET | `/_dev/components` | Development only; synthetic component shells. |
| GET | `/_dev/shell/<context>` | Development only; synthetic component shells. |
| GET, POST | `/access` | Admin metadata/actions or independent approver; no narrative access; service enforces each operation. |
| GET | `/account` | Authenticated current principal; available explicit contexts. |
| POST | `/account/context` | Authenticated; select only currently permitted context. |
| GET | `/auth/callback` | Validated state/nonce/issuer/audience/ACR, mapped active principal. |
| GET | `/cases` | Student context; current owner only, active archive scope; explicit safe projection. |
| GET | `/cases/<case_id>` | Student context; current owner only, active archive scope; explicit safe projection. |
| POST | `/cases/<case_id>/message` | Student context; current owner only, active archive scope; explicit safe projection. |
| GET, POST | `/cases/new` | Student context; current owner only, active archive scope; explicit safe projection. |
| GET | `/health/live` | Metadata-only liveness/readiness; no narratives. |
| GET | `/health/ready` | Metadata-only liveness/readiness; no narratives. |
| GET, POST | `/retention` | Admin metadata/holds/request or independent approver; offline-only execution. |
| GET | `/sign-in` | Public OIDC/S256 initiation; exact safe return target. |
| POST | `/sign-out` | Authenticated local session invalidation. |
| GET | `/staff` | Current staff context/team; officer assigned-only, manager/triage permitted metadata. |
| GET, POST | `/staff/archive` | Scoped current manager; metadata list; purpose-audited POST for archived initial content. |
| GET | `/staff/cases/<case_id>` | Current assigned officer or scoped manager; successful read audit required. |
| POST | `/staff/cases/<case_id>/action` | Eligible manager assignment/routing or assigned explicit start; expected version and guards. |
| POST | `/staff/cases/<case_id>/archive` | Scoped manager; Closed and expected version. |
| POST | `/staff/cases/<case_id>/claim` | Current scoped triage; atomic exclusive expiring claim, at most 30 minutes. |
| POST | `/staff/cases/<case_id>/communicate` | Current case policy per operation; manager-only reopen; version guard; notes separate. |
| POST | `/staff/cases/<case_id>/refer` | Active assigned officer; current team and deliberate minimal summary. |
| GET | `/staff/reassignment` | Current scoped manager; metadata only. |
| GET, POST | `/staff/referrals` | Current source access or approved-state target manager; decisions checked independently. |
| GET | `/staff/triage/<case_id>` | Current claimed triage; initial request/necessary identity only, audited. |
| POST | `/staff/triage/<case_id>/release` | Claim owner/current scoped authority; no later content. |
| GET | `/static/<path:filename>` | Local static assets only. |

## Business state machine

Submission → New (server-owned identity/team/reference/time). Eligible assignment leaves New unchanged.
Assigned start: New → In Progress. Question: In Progress → Awaiting Student plus message atomically.
Owner reply: Awaiting Student → In Progress; other active-state messages preserve status.
Assigned resume with reason: Awaiting Student → In Progress. Outcome-required closure: In Progress → Closed.
Scoped manager reopen: Closed → In Progress with reason and eligible assignee. No silent timeout closure.
Messages/notes on Closed reject; archive is separate from status. Corrections append to same-case own entry.

Referral: proposed → source_approved → accepted or rejected; source withdrawal is terminal before acceptance.
Target visibility starts at source approval, includes accepted/rejected, excludes withdrawn unapproved proposals.
Accept creates one separate New target case with selected summary and null assignee; source case is unchanged.

Lifecycle: active → archived only when Closed; hold blocks disposal. Old synthetic archived case →
pending disposal → independent approved → offline completed. Recheck actors, age, hold and links in transaction.
Real durations are unconfigured. Audit and minimal completed-disposal ledger remain; narratives are erased.

## Data and trust decisions

The 18 collection contracts and indexes live in app/repositories/schema.py. UUID string identifiers,
UTC timestamps and safe typed filters are required. Relationship integrity is service-enforced.
Version/account/team writes detect concurrent policy changes within transactions. Worker does not read
cases/messages/notes; restore credentials only access quarantine. Audit reads require a separate scoped
offline reader. The web role cannot modify historical audit rows.

Justified additions to the baseline: disposal_records preserves authorised erasure evidence for restore replay;
rate_limits supplies shared multi-worker counters; a separate restore-only DB prevents stale sessions/mail
from entering service. These implement existing retention/recovery/abuse requirements. No new cross-team
narrative sharing is introduced. Production HTTPS/KMS/offsite custody remain proposed.

See [current architecture](runtime-status.md), [threat evaluation](../security/risk-register.csv)
and [limits](../handbook/known-limitations.md).
