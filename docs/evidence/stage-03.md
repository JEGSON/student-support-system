# Stage 03 — runtime checkpoint evidence

Date: 2 November 2026 (Europe/London). Prior commit: `ddcfca1` (Stage 02).
Runtime changes belong to the enclosing runtime checkpoint commit. Operator/review:
Codex self-review; no independent review claimed. Fixtures: generated local realm,
bootstrap identities, separate dev/test database users; inline synthetic gallery v1.
No real student records or production integrations.

## Implemented and observed

- Flask factory, explicit configuration and no client-session fallback; safe public
  entry/sign-in-unavailable/error pages; real Jinja components; development-only
  component/student/staff gallery. No business endpoints or authentication bypass.
- `uv lock --cache-dir runtime/uv-cache`: resolved 17 packages after the initial
  sandbox DNS failure was retried with approved network escalation.
  `uv sync --frozen --cache-dir runtime/uv-cache`: installed 15 packages in the
  existing initially empty `.venv`. Python 3.14.7, uv 0.11.3, Docker Engine 29.0.1.
  Flask 3.1.3, PyMongo 4.19.0, python-dotenv 1.2.4, pytest 9.2.0 are locked.
- Official MongoDB 8.0, Keycloak 26.8.1 and Mailpit images downloaded and digest
  pinned in Compose. Docker Desktop was started with approved escalation.
- `python3 scripts/setup_local.py`: generated ignored local secrets without printing
  values. A repeated run exited 1 with “Existing .env preserved”; no rotation or
  overwrite occurred. `.env`, MongoDB keyfile and realm import paths are ignored.
- `.venv/bin/python scripts/start_dependencies.py`: after the fixes below, rerun
  reported replica set/users ready and **all required local dependencies ready**.
- `.venv/bin/python -m pytest -q`: **16 passed, 1 skipped**, 0.10s. The skip is the
  explicitly opt-in real runtime test, not a missing unit test.
- `RUN_RUNTIME=1 .venv/bin/python -m pytest -q`: **17 passed**, 0.19s. Actual local
  service checks included MongoDB primary, OIDC discovery and mail readiness;
  opposite-database reads denied for both credentials; a real synthetic transaction
  explicitly aborted and verified absent. No mock transaction result substituted.
- Tests cover missing/placeholder/short secret, debugger prohibition, wrong
  development/test database, production local/development config rejection, insecure
  TLS option rejection, safe Host/method/body/error responses, no cookie fallback,
  production/test gallery exclusion, escaped component content and safe dependency
  failure output/logging. These are partial V16 configuration evidence, not full
  release or identity/authorisation assurance.
- Final live HTTP probes: `curl --fail --silent
  http://127.0.0.1:5050/health/ready` returned `{"status":"ready"}`;
  the development component-gallery probe returned HTTP 200.
- `uv lock --check --offline --cache-dir runtime/uv-cache`: PASS, 17 packages
  resolved from the existing lock/cache without updating inputs. Documentation
  integrity: PASS, 82 traceability rows and 199 document links; static design check
  still passes. `git diff --cached --check`: exit 0. Staged content was checked
  against the generated secret values without printing them: no matches, and no
  `.env`, `runtime/` or `.venv/` files staged. No full security scan is implied.

## Failures, corrections and limits

1. Initial unit run: 1 failed, 9 passed, 1 skipped. Invalid Host left Flask without
   a URL adapter and the error template tried `url_for`. Corrected the 400 path to
   a safe plain response. Subsequent unit tests passed, then six relevant checks
   were added for TLS options/body/session fallback and the final suite passed.
2. Initial stack start: OIDC host port 8080 occupied. Port 5000 was also held by
   macOS Control Center. Switched only project defaults to 8180/5050; preserved
   unrelated services. MongoDB/mail loopback bindings remained unchanged.
3. Identity import failed on realm/file naming, then an empty file left in the
   persistent import directory. Corrected the filename and mounted a dedicated
   read-only import directory. Identity discovery now passes in the real test.
4. Mongo shell interactive stdin could continue after an error and print a success
   phrase. Changed bootstrap to `--file /dev/stdin` and proper nonzero error handling;
   caught the expected uninitialised-replica-set exception before initiating.
   Required readiness/transaction checks initially failed (503); they passed only
   after these corrections. The starter now waits for all dependencies.
5. Browser host remained unavailable. Native Chrome briefly connected and the
   public page's accessibility tree and one screenshot showed the actual styled
   landing page. Responsive toolbar interactions timed out/lost the window
   (`noWindowsAvailable`). No 390/768/1440 rendered inspection, keyboard-focus,
   reduced-motion emulation or repository screenshot evidence is claimed yet.
   The user said they would enable browser access; the latest inventory still
   reported “The browser access host is unavailable”.

**Stage 03 remains incomplete pending its rendered responsive verification.**
Do not advance to Stage 04 under the stage progression rule. Source/runtime checks
are preserved; V16 is partial, V14 remains unrun. Later service permissions, OIDC
sessions and production hardening remain explicitly future work. No production
readiness, third-party delivery, remote push or real-data processing is claimed.
