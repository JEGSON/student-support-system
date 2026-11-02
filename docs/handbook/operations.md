# Operational preparation and recovery

These procedures are local synthetic demonstrations. Production deployment, real
student processing and external email remain blocked by OD-02–07. Named operational
roles below are proposed responsibilities, not assigned real people.

## Production template

wsgi.py creates the Flask factory from externally injected environment only.
gunicorn.conf.py binds loopback with two eight-thread workers, no preloaded Mongo
client, 30-second timeout, bounded headers/line and metadata-only logs. Do not use
the development runner publicly. Prepare an HTTPS edge under an approved host;
when TRUST_PROXY=1, configure PROXY_HOPS=1 and the exact PROXY_TRUSTED_IP. Only one
X-Forwarded-For IP and X-Forwarded-Proto=https are accepted. Forwarded host/port/
prefix, lists, missing hops and untrusted peers reject. Keep the backend private.

APP_ENV=production requires non-development secret, distinct production DB with
TLS/no insecure options, HTTPS origins, approved OIDC authentication class/client
registration and shared Mongo rate limiting. Secure/HttpOnly/Lax cookies, CSRF,
CSP/no-store/HSTS and body limits are applied. Most forms cap at 64 KiB; large-text
submission/message endpoints cap encoded bodies at 128 KiB while text remains
10,000 characters. Runtime limits default to 600 reads/120 writes/30 identity
requests per minute, keyed by actor or trusted client IP; tune only from measurements.
Rate storage failure denies rather than bypasses protected work. Inspect the proxy
and operations tests before changing trust assumptions.

The public process retains only allowlisted web settings, not maintenance/audit/
worker passwords. The local developer account can still read its own private .env;
production needs separate runtime identities/secret injection and approved KMS.
Web DB credentials have no audit read/update/delete or history delete. Worker reads
outbox/contact/principal only, never case/messages/notes. Separate audit reader is
find-only. Schema, maintenance and restore operators remain privileged risks.

## Monitoring, rotation and incidents

Watch /health/live and /health/ready through trusted routes; readiness is metadata
only. Monitor authentication rejection, current-request IDs, denial/audit failure,
HTTP 5xx/429 rates, pool wait, outbox overdue/dead counts and worker liveness. Generic
notification alerts are reported by the local worker; production alert destinations
and on-call routing are unconfigured. Logs exclude URL/query/body/token content.
Authenticated HTTP denials carry attributed audit metadata; anonymous rejects are
fixed metadata logs. Auditing failure never grants content. A committed business
transaction remains intact after notification failure.

For compromised identity: disable/revoke through controlled administration, review
attributed audit history with approved scope, reassign cases and record actions.
For suspected app/DB compromise: isolate the service and worker, preserve protected
metadata evidence, involve security/privacy/safeguarding owners, rotate affected
secrets and restore only into quarantine. Do not copy narratives into tickets/logs.
No statutory notification deadlines or legal conclusions are invented here.

Rotate credentials through a controlled operator process: generate new secrets,
change the matching DB/provider credential, update injected web/worker settings,
revoke server sessions/auth attempts and restart affected processes. Session-token
rotation alone does not rotate DB credentials. Re-encrypt/newly encrypt backups
under a new key while retaining old keys until all dependent backup copies expire
under approved policy. Never print keys/passwords or put them in Git/argv/logs.

## Encrypted synthetic recovery

Keep key material separate from snapshot/ledger files. Examples (paths are ignored):

```sh
.venv/bin/python scripts/recovery.py keygen --key runtime/keys/recovery.key
.venv/bin/python scripts/recovery.py backup --environment development \
  --key runtime/keys/recovery.key --output runtime/backups/snapshot.enc
.venv/bin/python scripts/recovery.py ledger --environment development \
  --key runtime/keys/recovery.key --output runtime/ledger/latest.enc
.venv/bin/python scripts/recovery.py restore --key runtime/keys/recovery.key \
  --input runtime/backups/snapshot.enc --ledger runtime/ledger/latest.enc --ack-latest-ledger
```

Files are created exclusively (0600); choose a new name for a new snapshot rather
than overwrite. The private ledger must be refreshed/securely copied after every
completed disposal and before restore. The acknowledgement asserts operator review
of its authoritative latest state; encryption alone cannot prove freshness. A ledger
older than the backup is rejected. Store an independent ledger/key copy off the
failed host in a real operation; the demo does not provide off-site custody/KMS.

Restore targets only student_support_restore_test via its own credential. It refuses
normal app DBs/nonempty targets; the public app and worker cannot serve that DB.
Snapshots are authenticated/encrypted, bounded to 200 MiB expanded JSON and exclude
sessions, OIDC attempts, submission tokens and rate counters. Reconciliation replays
completed disposals and drops linked messages/notes/events/referrals/jobs/keys;
remaining referral links are detached. Restored sessions are empty and pending/
leased notifications become dead, preventing stale resend. Do not activate quarantine
until record integrity, ledger freshness, permissions and secret rotation are reviewed.
A partial restore remains offline; discard only the dedicated failed quarantine
through an authorised operator, reinstall schema and restart from empty. Idempotent
ledger reconciliation can safely repeat; never erase or overwrite development data.

Disposal execution requires approved state plus current distinct admin/approver:

```sh
.venv/bin/python scripts/dispose_synthetic.py --environment development --record LEDGER_UUID
```

Erasure is transactional and repeat-safe; holds or changed eligibility refuse it.
Business narratives are erased; minimal actor/target/time audit and completed ledger
persist. No real retention duration or case TTL is enabled. Future restored backups
must always reapply the latest ledger before any activation.

Proposed production targets are RPO 24 hours/RTO four hours. Local test measurements
are in stage-16/workload-recovery.json: 7.651-second restore, snapshot age 15.865 seconds
at recovery end, not proof of a daily backup schedule or a general real-world RPO.
A 200 MiB in-memory cap/single-node environment limits this implementation; production
backup scale, encryption-at-rest, off-site expiry, failover and ownership require review.
