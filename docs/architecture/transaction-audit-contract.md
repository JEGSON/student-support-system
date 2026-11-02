# Stage 07 transaction, audit and outbox contract

Historical stage checkpoint. For the completed local runtime and current additions,
see [as-built status](runtime-status.md) and [inventory](implementation-inventory.md).

2 November 2026. Implements ADR-03/06/09 without changing trust boundaries. Read
alongside the preserved eight-page draw.io baseline and identity/access contract.

`transaction` uses snapshot reads, majority commit, a five-second client deadline
and 1.5-second commit bound. PyMongo retries labelled transient failures and unknown
commit outcomes within that deadline. Callbacks contain DB work only. A labelled
transient failure is injected after a real database write to verify rollback/retry.
Unknown commit outcomes must be retried with the same submission key, never a new
key. This is not a claim of exactly-once network delivery.

`CaseTransactions.change` is an internal unit for future workflow services, with
mutation-only permission names, expected version, reference validation and atomic
case/history/audit/outbox effects. It is not an HTTP API or a complete lifecycle
state machine. Stage 09/10 services must validate their specific transitions before
calling it. Current case mutation HTTP endpoints remain absent. Actor/team/case
writes preserve Stage 06 revocation serialization. A stale version raises a review
conflict; no partial effects remain.

`idempotent` requires the caller to lock the actor in the same transaction. The
unique actor/operation/key hash returns the existing result for the same payload;
a different payload or expired key conflicts. Key cleanup is 24 hours; signed form
expiry must prevent recreation after cleanup. Payload fingerprints are private
SHA-256 hashes, not narrative text. Read/write audits use server-generated request
correlation IDs. Incoming correlation headers are ignored; response X-Request-ID
matches audits. Required reads must commit their audit before returning content.

`AuditWriter` accepts only fixed actions, target types, identifiers and changed
field names. No narrative/free metadata bag. Existing access changes now use it.
Public DB identities can insert audits but cannot read/update/delete them; case
history is find/insert only. `AuditReader` requires current reviewer context,
approved team/case scope and a nonempty bounded purpose, commits a read audit, then
uses a separate read-only credential. That credential is not retained in Flask config/environment or registered as a Flask client.
Read audit failure returns no content. Detailed case read services arrive in 08.

Local roles are explicit collection grants, with separate development/test secrets:

| Identity | Access |
| --- | --- |
| support_app / support_web_test | Managed business/session CRUD; history find/insert; audits insert only; outbox find/insert; no DDL |
| support_fixture / support_test | Trusted offline dev/test maintenance readWrite, including fixture reset; never a public app credential |
| support_audit / support_audit_test | Audit find only in their own environment |
| support_worker / support_worker_test | Outbox find/update; user contact/identity and service principal find; no case/messages/notes/audits or cross-environment access |
| support_schema | Offline dbAdmin for validators/indexes, no narrative find; privileged schema risk remains |

Worker user-collection access is collection-level, not field-level MongoDB masking;
a compromised worker credential can see identity/profile fields in that collection.
Future worker code must project only contact data. Root/maintenance/schema operators
remain privileged infrastructure risks. The developer process runs as the same local
account that owns the private setup file, so file access can bypass this separation;
production must inject only the web secret into an isolated web identity. External immutable audit copies, operational
monitoring, production separation/encryption and disposal are later stages. Local
roles are not a production deployment or tamper-proof evidence certification.

Outbox entries contain event key, recipient/case IDs, generic template and state,
never descriptions/notes. Unique event/recipient/channel prevents duplicate jobs.
NotificationJobs leases due pending or expired jobs for 60 seconds with a hashed
random lease token. A valid current lease can complete to sent, retry with bounded
exponential backoff, or become dead after five attempts/permanent failure. An expired
fifth lease is marked dead rather than stuck. No delivery network call exists here;
`sent` in tests denotes an explicitly simulated successful delivery result.
SMTP/email rendering, provider retries/alerts and contact policy arrive in Stage 11.

Sources: [PyMongo transaction callback/retry rules](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/transactions/),
[MongoDB user-defined roles](https://www.mongodb.com/docs/manual/core/security-user-defined-roles/).
