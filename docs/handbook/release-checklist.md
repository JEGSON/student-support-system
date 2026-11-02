# Local release and assessment checklist

This package is for local synthetic review only. The complete rubric, submission
instructions/deadline and institutional AI policy have not been supplied. Confirm
those with the assessor before submission; this is not certification of conformity.
FR-04/06 remain undefined. The AI-use statement discloses substantial assistance.

- Source, tests, uv.lock, configuration example, diagrams, evidence and runbooks are included.
- Local Git has meaningful incremental history. Git metadata is excluded from the ZIP;
  history is reviewed in the retained repository. A configured origin is not proof
  of remote publication/history. No push/upload was performed.
- .env, generated credentials/tokens, runtime, environments/caches, backups, volumes
  and package output are excluded. All fixtures/screenshots are synthetic.
- Build only from a reviewed clean commit: `.venv/bin/python scripts/package_release.py`.
  Output is dist/student-support-assessment.zip, SHA256SUMS and package-receipt.json.
  PACKAGE-MANIFEST.json inside records the exact source commit and per-file hashes.
- Run `.venv/bin/python scripts/check_release_secrets.py` before committing and
  `--archive dist/student-support-assessment.zip` after packaging. This compares
  actual private secret values; it supplements review, not universal secret detection.
- Extract into a new ignored runtime directory. Follow setup.md using a fresh frozen
  dependency environment; run unit, documentation and design checks. Compare every
  extracted file with the embedded manifest. Avoid launching another Docker stack
  with different secrets against the existing named volumes.
- Full Docker/OIDC/browser acceptance is checked in the retained checkout; extracted
  package checks are representative unit/configuration/docs checks, not a second
  full isolated deployment. Keep that distinction in assessment evidence.
- The external package receipt supplies checksum/size/commit for the actual ZIP;
  it is excluded from Git to avoid a self-referential checksum inside its own source.

Evidence is in docs/evidence/stage-16 and stage-18. Use testing-checklist.md and
handover.md for the finance/referral/control demonstration. Review known-limitations.md
before changing institutional policy defaults or considering a later release.
