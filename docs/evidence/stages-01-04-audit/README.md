# Stage 01–04 audit and cleanup

2 November 2026, Europe/London. Prior source commit: `07558b7`. Changes/evidence
belong to the enclosing audit commit. Codex self-review; no independent review
claimed. User explicitly limited work to Stages 01–04 and requested a checkpoint
before proceeding. Stage 05 and later were not implemented or newly installed.

## Stage coverage and code review

| Stage | Reviewed deliverable | Current result |
| --- | --- | --- |
| 01 | Existing checkout/history, architecture baseline, provenance/gaps, requirements, decisions, risks, backlog, AI/evidence records | Planning integrity check passes; missing assessment/institutional material remains explicitly open. |
| 02 | Annotated static design, shared tokens, component states, responsive direction | Static checks pass; 30 current runtime screenshots match previously reviewed images exactly. No new UI feature was added. |
| 03 | Factory/config/health/errors/Jinja, isolated dependencies, local-only setup and clean installation | Fixed runtime timezone decoding, bounded connection waits/pool, safe URL/port validation, runner import side effects and bounded bootstrap subprocess waits. Full tests pass. |
| 04 | Fifteen schema/index contracts, typed query helpers, reference checks, fixture/migration tools | Fixed required/null reference checks, reduced metadata lookups, added query deadline and archive-aware index. Actual validator/uniqueness/rollback/reset/privilege tests still pass. |

Ruff 0.17.3 standardised all 22 Python source/test/script files, removed unused
imports, organised imports and expanded dense one-line statements. Stable explicit
lint rules are configured in pyproject.toml. Three direct script entry points retain
justified E402 exceptions because they add the repository root before app imports.
The safe exception logger is now an explicit Flask subclass instead of a lambda.
No business feature, framework rewrite, password authentication or UI access bypass.

Initial lint output reported 58 findings, including safe automatically fixed
imports/style issues. Formatting and targeted corrections resolved remaining
findings; no unsafe automatic fixer was used. An initial patch failed context
validation and made no changes; it was reapplied against the formatted source.
No application regression test failed in the final audit run.

## Dependencies actually downloaded and installed

- `uv sync --frozen --cache-dir runtime/uv-cache` verified the current environment.
- Frozen all-group requirements were exported from uv.lock. Created ignored
  `runtime/stages01-04-clean-env` and installed **46 packages** offline from the
  downloaded cache using `uv pip sync --require-hashes`.
- Runtime: Flask 3.1.3, PyMongo 4.19.0, python-dotenv 1.2.4 and resolved transitives.
  Test: pytest 9.2.0, Playwright 1.64.1. Current quality tooling: Ruff 0.17.3 and
  pip-audit 2.10.1. Exact names/versions: [inventory](dependency-inventory.json).
- `python -m pip check`: **No broken requirements found**.
- `uv lock --check --offline --cache-dir runtime/uv-cache`: PASS (48 lock entries
  including virtual/platform-specific entries; 46 packages installed on this Mac).
- `docker compose --env-file .env -f infrastructure/compose.yaml pull`: MongoDB,
  Keycloak and Mailpit all Pulled; image digests remain pinned. No new real service.
- `PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers .venv/bin/python -m
  playwright install chromium webkit`: required binaries available locally.
- No Stage 05 Authlib/session implementation or later production/load tools added.
  Ruff and pip-audit are dev tools used by this cleanup, not runtime features.

## Actual tests/checks

Final full regression, executed from the **clean** environment:

```sh
RUN_BROWSER=1 RUN_RUNTIME=1 PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers BROWSER_EVIDENCE_DIR=docs/evidence/stages-01-04-audit/browser runtime/stages01-04-clean-env/bin/python -m pytest -q
```

**103 passed in 111.20s**; no skips in this full run. Includes actual local MongoDB
replica-set transactions and separate credentials, new required-reference/config/
timezone/pool/index-plan regressions, and Chromium/WebKit at 390/768/1440 widths.
Tests use synthetic fixtures only. The smaller initial unit-only run had 33 passes
and 70 opt-in skips; that was superseded by the complete run above.

- `ruff check app scripts tests wsgi.py`: PASS.
- `ruff format --check app scripts tests wsgi.py`: 22 files already formatted.
- `python -m compileall -q app scripts tests wsgi.py`: exit 0.
- `python3 scripts/check_foundation.py`: PASS, 84 traceability rows and 219 links
  before this audit's extra documentation links; final link count can increase.
- `python3 scripts/check_design.py`: PASS.
- Clean-environment startup script and actual local readiness: PASS. Migration
  scripts installed the additive active-case index in development/test without
  dropping indexes, resetting fixtures or rotating existing credentials.
- [Query-plan summary](query-plan-summary.json) records only counts/index metadata.
  The test asserts IXSCAN and no COLLSCAN/blocking SORT with an explicit hint;
  this is a tiny fixture check, not a workload or capacity result.
- Current browser evidence is isolated under `browser/`, preserving historical
  Stage 03 records. All **30 screenshots are byte-identical** to those previously
  reviewed. Contexts/fixture servers close after tests; no personal browser profiles.
  Routine runs now default to ignored runtime/browser-evidence; explicit evidence
  output is restricted to repository runtime/evidence directories.

Dependency advisory check:

```sh
.venv/bin/pip-audit --local --strict --progress-spinner off --format json --output docs/evidence/stages-01-04-audit/dependency-audit.json
```

**No known vulnerabilities found**, 46 installed Python packages, zero reported
advisories. [Machine-readable report](dependency-audit.json). This is a dated
Python-package advisory check; it does not certify container images or future code.
Only package names/versions were sent to the public advisory service.

## Scalability judgment and scope

See `../../architecture/scalability-review.md`. The foundation supports continued
incremental growth through per-process pooled connections, explicit resource bounds,
indexed keyset pagination and separated layers. No load capacity, high availability,
production deployment or full security/accessibility acceptance is claimed. Stage
15/16 hardening/load/recovery work is still required later. Missing institutional
policy remains open; synthetic development may continue when the user resumes.

No remote push, deployment, third-party message or real student processing occurred.
Stop here before Stage 05 as requested. The code, dependencies and evidence for
Stages 01–04 have been checked and are ready for the next development stage.

Final documentation integrity check: **85 traceability rows and 225 document links
pass**. Staged whitespace check passes. Staged content was compared against current
generated local secret values without printing them: no matches; `.env`, virtual
environments, browser binaries and runtime state were excluded. Only synthetic
screenshots and non-sensitive package/index metadata were added as evidence.
