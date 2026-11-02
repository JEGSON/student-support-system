# Stage 01–04 scalability review

2 November 2026. Scope: implemented foundation, not production capacity certification.
The modular Flask/Jinja monolith remains appropriate for this demonstration. It
keeps deployment/simple request processing together while separating persistence,
reference integrity, presentation and the future identity/policy/business layers.
Stages 01–02 intentionally deliver planning/design artefacts; Stages 03–04 contain
working runtime and persistence code. No empty feature module is claimed implemented.

| Concern | Current mechanism and audit change | Verification / remaining limit |
| --- | --- | --- |
| Database connections | One reusable MongoClient per application instance; explicit pool size 20 initially, configurable 1–100; 1.5s pool wait and bounded network waits. UTC-aware decoding now consistent with CLI clients. | Options/regression tests pass. Budget connections across future WSGI processes; 20 is an initial tuning choice, not a measured optimum. |
| Case lists | Ownership/archive filter, 1–100 page size, stable timestamp/id keyset pagination, 1.5s server query deadline. Added archive-aware compound index without dropping baseline indexes. | Actual hinted IXSCAN plan supports the active-case sort without COLLSCAN/blocking SORT on fixtures. Representative optimiser/load behaviour still needs measurement. |
| Integrity lookups | Typed fixed queries, required/non-null reference checks, per-validation metadata reuse and projections that exclude narratives/contact data. | Negative/reference tests pass. These are integrity controls; caller permissions and concurrent revocation guards arrive later. |
| Write consistency | Replica set; transactional fixture setup/reset and actual rollback checks; explicit validators/unique indexes. | Domain transaction coordinator/version contention tests remain Stage 07/feature work. |
| Startup/resources | Explicit config, missing-secret failure, idempotent local services, timed subprocess/bootstrap/readiness attempts and safe failures. Runner now has an import-safe main guard. | Clean environment and actual local CLI startup passed. Production process management is not implemented. |
| Sensitive responses | No-store, no third-party assets/scripts, bounded body size, separate note collection, development-only synthetic gallery. | Current runtime/browser tests pass; no case-content endpoints yet. |
| Deployment growth | App factory and repository/service boundaries support later WSGI processes; sessions/outbox schema prepared for shared state. | Server-side sessions, shared rate limiting, restricted worker/audit roles, proxy, backups and production operations are still pending. |

The added active-case index is `cases_v1_6` on student_id, archive_state,
updated_at DESC, id DESC. Existing indexes are retained to avoid an unreviewed
removal; assess redundant index write/storage costs against the later workload.
Do not install schema from public request paths. Metadata projections reduce both
unnecessary sensitive reads and repeated work in reference validation.

No 20,000-case/100,000-message/50-user/15-minute workload, p95 capacity benchmark,
failover or multi-instance recovery exercise was run in this audit. Those remain
the proposed later-stage evaluation, not achieved or institution-approved capacity.
A single-node local replica set proves transaction availability, not high availability.
A passing unit/integration/browser suite is not production readiness or full WCAG
conformance. Stage 01–04 foundation is verified for continuing development only.

Primary references reviewed during changes:
[PyMongo connection pools](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/connect/connection-options/connection-pools/),
[aware dates](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/data-formats/dates-and-times/).
Actual observations: `../evidence/stages-01-04-audit/README.md`.

## Stage 05/06 update

Shared hashed Mongo sessions now support multiple app instances without in-process
identity state. Indexed revocation by user and pending/scoped grant queries are
implemented; administration lists are bounded to 100 and need pagination for larger
institutions. The five-second transaction guard intentionally serialises team writes
for correctness. Team contention, shared rate limiting, production WSGI and workload
capacity remain unmeasured; see `identity-access-contract.md`.
