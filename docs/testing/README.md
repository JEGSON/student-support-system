# Traceability and verification

`traceability.csv` maps FR/SR/BR requirements, workflows, threats and verification
IDs. Space-separated IDs in a cell are multiple references. Blank cells mean not
applicable or no evidence yet; they never mean a test passed. `primary_stage` is
the planned main implementation stage; threat/test summary rows at Stage 16 mark
consolidated evaluation. Relevant tests must still run with each earlier feature.

The mapping is an engineering coverage proposal. The verification plan retains
the baseline method and traceability wording verbatim; the traceability table
expands mappings for feature planning. Full assessment wording remains pending.
FR-04/06 are unresolved, without fabricated test coverage. BR-01–08 interpret the
grouped reference key in order: ownership; assignment and timestamps; accountable
ownership; eligible assignment; distinct visibility; correction history; separate
archiving; restricted disposal. BR-09 is concurrency; BR-10 urgent escalation.
Confirm these summaries against the original requirements when supplied.

Status vocabulary: `planned` (no implementation), `unresolved` (definition missing),
`planning recorded` (contract documented, not evidence that runtime or GitHub
requirements are satisfied). Future implementation can use `partial`, `verified`,
`failed`, `blocked` and `deferred` with concrete implementation and evidence links.
Split rows when different tests have different outcomes; do not promote an entire
requirement based on one happy path. Preserve prior failures in evidence records.

`verification-plan.csv` lists V01–V16 and their expected methods. Statuses are updated only with observed, scoped stage evidence. Stage 01's documentation integrity check is not one of those runtime
verifications. No placeholders under `tests/` count as executable tests.
