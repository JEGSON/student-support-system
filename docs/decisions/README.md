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
