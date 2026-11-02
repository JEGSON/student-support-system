# Stages 18–19 release and handover evidence

Candidate source commit cbdc3d6e405d1c47f7e4003ac7a8b1381ce81f4d was packaged,
extracted into a fresh ignored directory, and all 585 source file hashes matched
its embedded manifest. Two builds from that clean commit produced identical SHA256:
f6d1b9d5ab35aaec7a87ba7641988a3650e1812c84636df96be3a25a9b6bbe48.
Candidate archive size 36,423,049 bytes. Actual private-secret comparison: 30 values,
zero matches in candidate source/decompressed archive. Review JSON/XML are alongside.

Extracted uv.lock exported into hashed requirements, and a new environment installed
55 packages with --require-hashes. Private setup generated .env with 0600 permissions;
no credentials or Git metadata were present in the extract. 71 unit tests, foundation
links/XML, design checks, Ruff lint/format and Flask landing/components/liveness smoke
all passed. A second Docker stack was intentionally not started against shared named
volumes; full OIDC/database/browser acceptance is the retained-checkout 280-pass run.
Candidate checks do not claim another full live-stack clean deployment.

Final documentation refinements reconcile workflow wording/status and historical
checkpoint banners. The final archive is rebuilt from the later clean handover
commit and the same extraction checks are repeated. The external dist/package-receipt.json
and SHA256SUMS identify the actual final source commit/archive checksum, avoiding a
self-referential checksum in the tracked source. Candidate hash above is historical.

Stage 19 delivers handover status/owners, operating responsibilities, finance and
both required referral scenarios, unauthorised denial and repeatable notification-
failure demonstration, plus prioritised next-release gates. Full rubric and AI-policy
format are missing; assessment readiness is provisional. Live readiness remains blocked
by institutional policies/operations and human review gaps. No push/upload/deploy,
external email or real student information occurred.
