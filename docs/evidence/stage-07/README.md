# Stage 07 verification

2 November 2026; baseline b3d39c2. Local authenticated MongoDB 8.0 replica set;
Python 3.14.7 and existing locked dependencies. No external email, deployment or push.

Command: `RUN_RUNTIME=1 .venv/bin/pytest tests/unit tests/integration -q`.
Observed initial gate: **183 passed in 5.28s**, no skips. Final role-isolation gate
passed **183 tests in 5.98s**, no skips, saved in `pytest-results.xml`.

`test_transaction_foundation.py` verifies real rollback after audit/outbox failure,
competing versions (one commit/one conflict), transient retry after actual database
write, submission-key replay/payload conflict, duplicate outbox key rollback,
append-only DB audits/history, explicit scoped audit reader and read-audit failure,
worker collection restrictions, job lease/retry/dead/stale-token behaviour and
mutation-only permissions. Existing Stage 01–06 checks continue to pass.

A separate maintenance identity preserves explicit fixture setup/reset while
ordinary web identities lose broad readWrite. Worker/audit credentials are separated
by environment. No schema/collection count change: additive payload_hash and
lease_hash fields extend existing strict contracts. See
`../../architecture/transaction-audit-contract.md` for exact semantics and limits.
No case HTTP pages were exposed before this gate.
