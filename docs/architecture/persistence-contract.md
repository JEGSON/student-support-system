# Persistence contract v1 — Stage 04

This extends the proposed v1.0 design baseline for the synthetic demonstration.
Canonical executable contracts: `app/repositories/schema.py`. No public case
feature or access-policy implementation is introduced in Stage 04.

## Representation and data model additions

Identifiers are canonical lowercase UUID strings, stored in MongoDB `_id` and
reference fields. Normal application IDs will use server-generated UUID4; fixture
IDs use deterministic UUID5 under a labelled synthetic namespace for repeatability.
Neither form is an access credential. Human references are separately unique.
UTC BSON dates are written using aware datetimes; schema/fixture clients decode
aware UTC. `london_time` displays Europe/London including GMT/BST; naive datetimes
are rejected. Types/enumerations/lengths are in strict validators, with unknown
fields rejected. Service input helpers trim plain text and reject objects/operators.

| Collection | Contract and principal invariants/indexes |
| --- | --- |
| users | Unique issuer/subject, unique student reference when present; active/disabled and allowlisted global roles. New `authorization_revision` integer supports future revocation guards. |
| teams | Unique name, allowlisted category scope, active flag and new `authorization_revision`. |
| memberships | Unique user/team/role; triage/officer/manager; grant/revocation metadata and user/active lookup. |
| cases | Unique reference; typed student/team/assignee; New/In Progress/Awaiting Student/Closed; version ≥1; archive separate; holds. Scoped student/team/assignee pagination indexes. Optional originating referral unique when present. |
| messages | Plain text 1–10,000 characters; author/time, optional correction reference; ordered case/time/id index. Student-visible retrieval remains a future explicit projection. |
| internal_notes | Separate collection and retrieval; 1–10,000 characters; superseding note reference; ordered case/time/id index. Never embedded in message documents. |
| case_events | Allowlisted event names and change metadata; no arbitrary body field; ordered case/time/id index. Future student timeline needs a safe projection. |
| referrals | Purpose ≤1,000 and selected summary ≤3,000; source/target references and approval/decision fields; target-team/status/time index. States are structural proposals pending Stage 12 state-policy review. |
| audit_events | Exactly one actor or service principal; metadata-only allowlist, no narrative field; target/time and actor/time indexes. Append-only database privileges arrive in Stage 07. |
| notification_outbox | Unique event/recipient/channel; generic template key and delivery state; state/next-attempt index. No narrative/template parameter bag. Worker permissions/leases/retries arrive later. |
| sessions | Unique SHA-256-format token hash; explicit idle/absolute/authentication times and revocation. TTL cleans absolute expiry only; Stage 05 must check every request. No usable tokens seeded. |
| submission_keys | Unique user/operation/key hash; expiry cleanup index; result reference. Current result type is case for the implemented persistence contract; revise explicitly if later message-idempotency scope uses message results. |
| triage_claims (new) | One record per case, claimant/team/time/state/version and authorisation revision. No TTL-based access; future policy enforces the ≤30-minute claim and current membership. |
| privileged_grants (new) | Target user/team/role, requester, reason, state and independent approval metadata. Stage 06 must enforce independent approval, scope and bootstrap. Merely inserting a record never grants application access. |
| service_principals (new) | Unique service name, kind notification_worker, active flag/revision. A fixture identity is not a usable database/worker credential. |

All contracts permit an optional server-only `fixture_version=synthetic-v1` marker
for controlled fixture/reset operations. It is never a public form field. Runtime
service forms must use explicit allowlists; database schema is not a permission
boundary. Privileged workflows, state transitions, approvals, timestamp ownership
and concurrency checks remain service responsibilities in their authorised stages.

## Reference and query boundaries

`app/services/references.py` checks referenced records through fixed server-owned
field/collection mappings. Case integrity also checks student role, active team/
category routing and active eligible assignee membership; corrections cannot point
to another case's message/note. These are integrity checks, not an authorisation
policy or a complete workflow implementation. Future mutation services must invoke
them within their transaction alongside permission/version checks. MongoDB has no
relational foreign-key enforcement; direct privileged database writes can bypass
service integrity. No public raw-document insert/update API exists.

`Repositories.student_cases` builds a scoped ownership/archive filter from a typed
UUID, bounds page sizes 1–100, orders by updated_at DESC and id DESC and uses a typed
datetime/id keyset cursor. Operator objects, malformed IDs and client filters are
rejected. Internal repository documents must never be serialized directly to a
student/staff response. T05/T06 projections and read-audit controls remain later work.

## Schema setup and upgrades

A separate local `support_schema` identity has dbAdmin only on development/test,
with no user/role-management privileges; its generated password is ignored.
Application/test identities retain separate database readWrite roles for now.
The Flask factory never installs/changes schema automatically. Trusted setup does:

1. Create absent managed collections with strict/error validation.
2. Use collMod on existing managed collections to install the v1 contract.
3. Create named v1 indexes idempotently; conflicts fail rather than drop/rebuild.

DDL/index setup is not a multi-collection atomic migration. Before a later contract
change, record a new version/decision, review data compatibility/index conflicts,
back up synthetic development data if needed, test on the isolated replica set and
rerun the migration after interruption. New validators do not certify historical
records: validate/backfill existing data explicitly before tightening a contract.
Do not drop indexes/collections or bypass validation to force a failed upgrade.
No production migration is authorised or supported by these local scripts.

Primary documentation checked: [MongoDB schema validation](https://www.mongodb.com/docs/manual/core/schema-validation/),
[PyMongo indexes](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/indexes/),
[transactions](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/transactions/),
[built-in roles](https://www.mongodb.com/docs/manual/reference/built-in-roles/).

## Stage 01–04 cleanup audit

The application MongoClient now decodes aware dates consistently with CLI clients.
Reference guards reject missing/non-nullable references before database writes and
read only reusable integrity metadata, excluding note/message bodies and contact
fields. An additive cases_v1_6 index includes archive_state for the actual active
keyset query; baseline indexes were preserved. Case queries now have a 1.5s server
execution bound. See `scalability-review.md` for evidence and limits.
