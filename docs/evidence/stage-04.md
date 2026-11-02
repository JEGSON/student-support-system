# Stage 04 — database contracts and fixtures

2 November 2026, Europe/London. Prior source: `0b4f5c2` (Stage 03 complete).
This record refers to its enclosing Stage 04 commit. Codex self-review only.
Actual authenticated single-node MongoDB 8.0 replica set, local development/test
identities, schema identity and synthetic-v1 fixtures; no mocks for transactions.

## Implemented and executed

- Fifteen strict collection validators and named indexes, typed query/input/date
  helpers, reference integrity guard and transactional idempotent synthetic fixtures.
  Added auth revisions, claims/grant metadata and a worker-principal contract.
- Separate dbAdmin-only local schema identity provisioned using a generated ignored
  secret. Existing app/test credentials preserved; their opposite-database denial
  test still passes. No database root credentials added to application configuration.
- Schema installed twice in the actual test fixture to verify repeatability; seeded
  27 synthetic records. No working OIDC/password/token fixtures. Ran documented CLI
  schema/seed commands for development and testing successfully (15 contracts each).
- `RUN_RUNTIME=1 .venv/bin/python -m pytest -q`: **79 passed, six skipped in 0.76s**.
  Six browser configurations are opt-in and unchanged from the successful Stage 03
  run; they were not rerun for this persistence-only increment. No UI changed.
- Actual tests cover every collection's valid BSON roundtrip in an aborted real
  transaction, unknown fields/wrong IDs, enum/type/length/whitespace violations,
  all required unique identity/student/membership/reference/hash/outbox keys and
  originating-referral uniqueness; index installation; idempotent fixture counts;
  nonexistent/forged/cross-case references; ineligible assignee/routing; bounded
  stable pagination with tied timestamps; malformed IDs/operator objects; London
  winter/summer display; reset preserving unlabelled data and rejecting dependants.
- Initial focused database run failed because the test expected schema code 121 for
  an operator object in `_id`; MongoDB rejects that earlier with reserved-field
  code 52. Corrected the expectation and separately tested wrong scalar ID type as
  a validator rejection. Focused rerun: 41 passed in 0.27s; expanded suite above
  includes the additional limits/referral/reset checks. The preceding expanded run
  had 78 passes; adding the privilege-separation check produced the final 79 above.
  That check confirms application credentials cannot collMod the schema and the
  schema identity cannot read case documents.
- Frozen lock check and static design checks pass; no new runtime package added.

## Limits and next stage

Schema/type/index success does not establish service authorisation, OIDC verification,
workflow/concurrency/audit controls or production acceptance. Reference guards must
be called by future policy-controlled mutation services inside transactions; direct
privileged DB writes can bypass them. dbAdmin migration identity is separate from
application roles; collection-level audit/worker restrictions remain Stage 07.

Retention durations remain unset; no cases/claims TTL disposal. Fixture reset is an
explicit isolated synthetic operation, not a real-data disposal process. Missing
assessment/institutional policy remains open. V07/V10 have scoped partial evidence;
full later-stage verification remains pending. Stage 04 complete; next is Stage 05
OIDC authentication and server-side sessions. No remote push or deployment occurred.
