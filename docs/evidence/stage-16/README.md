# Stage 16 integrated evaluation

2 November 2026; synthetic, loopback-only application. Workload runtime loaded
application revision 9361c1a. Later denial-audit and referral visibility fixes were
regression-tested separately; they do not add work to the successful student
read/write paths measured here. No production capacity certification.

## Observed 15-minute workload

- Cohort: 20,000 new synthetic cases; 100,000 starting
  messages; 50 pre-provisioned authenticated student users. Retained four unrelated
  canonical fixture cases and one fixture message were excluded from cohort queries.
- Actual duration: 900.498 seconds; 88,407 business requests.
- Reads 61,950, writes 26,457; 70.07% reads (planned 70/30).
- p50 57.19 ms; p95 163.31 ms; 98.18 requests/second.
- Unexpected responses: one GET 503; 0.0011%. No write errors recorded.
- Both proposed targets met: p95 below 2,000 ms and unexpected errors below 1%.

Gunicorn 26.2.0, two workers/eight threads each; Mongo pool 20/worker; 0.5-second
per-user think time; shared limits 600 reads and 120 writes per user/minute.
Apple M4, 16 GiB memory, 10 logical CPUs; local authenticated single-node MongoDB
replica set in Docker. Payloads are 168-character synthetic descriptions/messages;
reads use bounded latest-message views and indexed own-case queries. Real OIDC/SMTP
latency, staff/referral load, failover and operational internet traffic are excluded.

The explicit offline harness seeded opaque hashed sessions/signed forms before
measurement; every timed request still traversed normal authentication, current
policy, CSRF, transactions/audits and the WSGI HTTP stack. No app bypass endpoint.
A small security probe and local schema/fixture maintenance also ran during the
timed interval. These are evaluation-environment limitations. Logs showed two
long server durations around the lone 503; metadata does not establish its root
cause. Do not relabel this as zero failures. Repeat with host/database tracing on
a dedicated environment before real sizing. All benchmark records were cleaned.

Query evidence in workload.json shows bounded IXSCAN plans for student ownership/
archive keyset and case-message ordering, with examined rows/keys recorded.

## Recovery and security

The measured dataset was then encrypted and restored into the quarantined DB:
20,004 total cases and 126,458 messages; restore 7.651 seconds. Snapshot/ledger
capture took 5.399 seconds; snapshot age at recovery completion was 15.865 seconds.
Sessions and pending notifications were zero after reconciliation. This meets the
proposed four-hour restoration target for this synthetic image; daily backup
cadence/real 24-hour RPO are not proved. Small recovery tests separately exercise
disposal-after-snapshot replay, legal holds, wrong-key rejection and idempotent replay.

Project-owned explicit HTTP probe: 25 passed, zero failures. Scope was only
127.0.0.1:5052 application routes, never identity/SMTP providers. It is a bounded
negative probe, not a comprehensive external pentest. Read security-probe.json.

The advisory report and final result XML are alongside this document. Secrets
are checked against prospective tracked/package files before release. The final
regression covers identity, scope, lifecycle, worker failures, referrals, disposal,
proxy/rate limits, encrypted recovery and responsive student/staff flows.

## Findings and limitations

Fixed during review: authenticated denials lacked durable metadata auditing;
withdrawn unapproved referrals could appear in target inboxes; outgoing summaries
needed current source access; added demo staff initially failed to seed because
of an indentation error. Targeted regressions and the final suite verify corrections.
The full assessment rubric, undefined FR-04/06, institutional AI policy, identity/MFA,
privacy/retention/safeguarding and production ownership remain unresolved.

Final-gate fixes: upgraded dev-only Pillow from 12.3.0 to advisory-fixed 13.0.0;
the refreshed audit reports zero known advisories. Identity test teardown now
removes only request-correlated denial metadata it generated, so a later safe
fixture reset does not orphan records. The reset guard itself remains unchanged.

Final consolidated regression: **280 passed, zero skipped/failures/errors, 181.05 seconds**.
A following fixture-reset plus identity rerun passed nine checks, demonstrating
repeatable teardown rather than weakening the safe-reset dependency guard. Fresh
hash-checked Python environment: 55 packages installed; 71 unit tests passed.
Final scoped probes were rerun on a temporary owned loopback WSGI test server
with the restricted web DB identity: 25 passed; no provider scanning.
