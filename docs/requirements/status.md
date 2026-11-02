# Requirements planning status

The design baseline is in `../architecture/student-support-secure-design.html`.
Stage 01 extracted the requirements into `register.csv` and mapped coverage in
`../testing/traceability.csv`. All application controls remain unimplemented.

Open institutional decisions include identity integration, access owners,
privacy grounds, retention, safeguarding and hosting. Review the full rubric,
remaining attachment and AI policy before finalising assessment scope.

## Provenance

The user contract confirms Python, Flask, MongoDB, SSDLC, GitHub version-control
evidence, security testing, documentation and an accurate AI-use statement for this
project. The baseline reports that the assessment permitted SQLite or MongoDB;
the user and ADR-03 select MongoDB. These are confirmed project constraints, not
independently verified quotations from the missing complete assessment pack.

The baseline's requirement key defines FR-01–03, FR-05 and FR-07–13, SR-01–11
and BR-01–10. FR-04 and FR-06 are not defined in the supplied baseline. They are
explicit unresolved placeholders, not new features. Full original requirement
wording and institutional policy remain subject to OD-01/03 review.

WF-01–11, ADR-01–09, T01–T12, V01–V16, relationship rules, limits, expiry periods,
retention framework, performance/recovery targets and WCAG goal are proposed
engineering baseline choices. No performance or compliance claim has been tested.
Institutional policy is never inferred from these choices. The register preserves
identifiers and marks provenance rather than silently promoting proposals.

Deferred scope: uploads, unrestricted exports, historical migration, production
student-record integration, broad reporting dashboards, automated eligibility or
AI risk scoring, emergency break-glass and offline interaction. Reconsideration
requires explicit scope approval and threat/privacy design review.
