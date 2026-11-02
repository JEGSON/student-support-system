# Stage 01 — foundation evidence

Date: 2 November 2026 (Europe/London). Scope: repository and documentation only.
Operator: Codex; self-review, no independent reviewer. Source: the first foundation
commit enclosing this record; resolve with `git log -- docs/evidence/stage-01.md`.
The checkout had no commits at entry, so there is no preceding source commit.

## Initial inspection

- Working location: existing `2026-11-02/go/student-support-system` checkout.
- `git status --short`: scaffold files untracked; no tracked changes to overwrite.
- `git log`: no commits on `main`. `git remote -v`: no configured remote.
- Existing Git author identity was configured; it was not changed.
- Parent/project AGENTS.md search: none found. The available user-level
  `/Users/wealth/.codex/AGENTS.md` was empty.
- `python3 --version`: Python 3.14.7. Platform: local macOS shell, zsh.
- No synthetic account/data fixtures exist; fixture version: not applicable.
- The three baseline artefacts were read. Copies were present in the repository;
  the HTML gallery's eight PNG dependencies were absent and have been copied from
  the supplied architecture package without regenerating or modifying the design.

## Verification scope

The integrity checker validates identifier coverage/references, CSV shape, local
documentation links/HTML fragments, draw.io graph references and PNG signatures.
This does not assess diagram rendering or accessibility. No UI was created or
visually verified. No application, dependency installation, authentication,
database, transaction or security test has run. V01–V16 remain not run.

The registers distinguish confirmed user constraints from proposed controls and
unresolved institutional policy. FR-04/06 remain undefined. BR summaries interpret
the grouped baseline reference key and require confirmation with original evidence.
Missing full rubric, first attachment, deadline and AI policy are OD-01; no
contents or deadline have been invented. OD-02–08 remain open for their stated scope.

## Actual checks and results

- `python3 scripts/check_foundation.py` — PASS: 41 requirements/constraints,
  11 workflows, 12 threats, 16 planned verifications, nine ADRs, eight ODs and
  18 backlog stages. PASS: 80 traceability rows, 59 document links, eight diagram
  graphs and eight PNG assets. The script checks CSV source links additionally.
- `git diff --check` — exit 0. Because the incoming tree was untracked, the staged
  whitespace check below is the meaningful full-content check.
- `git diff --cached --check` — exit 0 after explicitly staging the scaffold,
  planning documents, checker and supplied previews. Reviewed staged file listing;
  no environment directory, populated secrets, data or dumps included. Reran
  `python3 scripts/check_foundation.py` against the final documents: PASS with the
  same counts above. Local commit only; no remote push.
- `git check-ignore .venv/ignored .env .env.local runtime/data data/cases.json
  backups/backup.dump test.key sample.log` — all eight paths ignored.
  `git check-ignore .env.example` — exit 1/no match, as expected for the example.
- Ad hoc byte-comparison using `Path.cwd()` and SHA-256 — PASS: the three repository
  design files exactly match the supplied outputs, and all eight preview files
  exactly match the supplied package. An initial attempt using `Path('.')` with
  `.parent` failed because it resolved the sibling path incorrectly. Corrected
  the check path and reran; no repository content changed for that correction.
- Ad hoc candidate-file review excluding `.git` and `.venv` — 65 files; no private-key
  headers, AWS access-key IDs or GitHub token patterns found in text files. No Python
  application files exist under `app/`. `.env.example` contains placeholders only.
  This narrow heuristic plus manual configuration review is not a full secret,
  dependency or security scan; those remain planned with the runtime.

Baseline SHA-256 values:

```text
student-support-secure-design.html dcedae3d4310ba4de39dfb61b0db694b07fb664d6147708e141af095ba49ba82
student-support-architecture.drawio 3e35a1bb4424556989f0c9ecec754aa01fc433bcc8623839b9a4c0ae6cb2d6cc
architecture-overview.html 7a28278655b897b726f2fc1a048aa461ed5bb836fc59d1c5def72af4141617d5
```

Stage 01 completes the documentation foundation only. Missing assessment material
and institutional policies remain open with owners and practical gates. No
application security assurance, remote history or production readiness is claimed.
