# Architecture decisions

ADR-01 through ADR-09 are recorded in the design baseline. Preserve their
identifiers when extracting decisions into separate records. Record context,
choice, alternatives, consequences and review triggers for each new decision.

`architecture-decisions.csv` extracts all nine proposals with consequences and
review triggers. They are demonstration engineering decisions, not institutional
approval. In particular ADR-03 selects a real MongoDB replica set and ADR-04
requires OIDC with an isolated synthetic provider until institutional registration.
There is no approved local-password alternative.

`open-decisions.csv` records OD-01–08, accountable owner roles, demonstration and
production impacts, interim choices and resolution evidence needed. Owner roles
are proposed responsibilities; no individual has been contacted or assigned.

Stage 01 delivery decision: reuse the existing uncommitted scaffold, restore its
missing preview assets from the supplied package, and make a meaningful local
foundation commit after document checks. No architectural deviation is introduced.

Stage 02 UI decision: adopt the proposed warm neutral/navy/teal palette, system
fonts, 1200px content width, labelled mobile queue cards and separate amber notes
panel. `../design/README.md` specifies tokens and permission-aware information
architecture. No framework/policy change. Static prototypes are design artefacts,
not authenticated application routes; rendered inspection is still limited.

Stage 03 runtime choices within ADR-01/02/03/07/09: uv lock and the existing Python
3.14 environment (tested 3.14.7) instead of provisioning the earlier proposed 3.13;
Flask 3.1.3/PyMongo 4.19.0; digest-pinned MongoDB/Keycloak/Mailpit; generated private
local secrets; loopback ports 5050/8180 after preserving occupied 5000/8080. MongoDB
single-node `rs0` advertises localhost; host application uses directConnection for
this development topology. Production must use its separately reviewed topology.
See `../development/local-runtime.md` and `../architecture/runtime-status.md`.
No institutional policy or business access boundary changed. Audit/worker database
privileges are still Stage 07 work before business features; initial database-level
readWrite roles are isolated between development and test. Responsive verification
remains an unresolved Stage 03 gate, not an accepted accessibility claim.

Stage 03 redo: user explicitly approved isolated Playwright browser checks after
native connection failures. Locked the development tool and used ephemeral browser
contexts/loopback fixture servers, with external requests blocked and no personal
profiles. This verification choice preserves ADR-01/02/03/07/09. The reviewed shared
CSS permits tablet actions to wrap without compression. Local runtime database URIs
are restricted to loopback to prevent accidental external-data access. Scoped
results and limitations are in `../evidence/stage-03-recheck/README.md`.

Stage 04 schema decisions: canonical UUID `_id` strings; UTC BSON dates; explicit
strict/error validators/indexes; deterministic labelled synthetic fixtures; a
separate local dbAdmin schema identity. Added user/team auth revisions and separate
triage_claims, privileged_grants and service_principals contracts. These are proposed
engineering additions, not university policy. `../architecture/persistence-contract.md`
records fields, indexes, service integrity boundaries and non-atomic migration limits.
Fixture reset rejects dependencies outside its version. No case-content web access
or Stage 06 approval/authorisation behaviour is implemented by this contract alone.

Stage 01–04 audit: retain the modular monolith. Use an initial configurable 20-entry
per-process pool and 1.5s pool/query bounds, aware UTC decoding, metadata-only reused
reference lookups and an additive archive-aware case index. These are development
bounds, not measured production sizing. Preserve baseline indexes until workload
analysis justifies removal. Locked Ruff/pip-audit support current cleanup and package
checks. `../architecture/scalability-review.md` records trade-offs and remaining
load/production work. No authentication, crypto or institutional-policy substitution.

The current ADR status reflects local implementation through Stage 19; production
parts remain conditional. The as-built runtime/inventory records the disposal
ledger, shared counters and restore quarantine added to implement existing controls.
