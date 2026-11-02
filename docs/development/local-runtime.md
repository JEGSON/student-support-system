# Local synthetic runtime — Stages 03–06

Requires Docker Desktop/Engine with Compose v2, Python 3.14 and uv. Tested on
macOS with Python 3.14.7, uv 0.11.3 and Docker Engine 29.0.1. The existing empty
virtual environment was reused. Python 3.13 remains within package metadata but
was not tested; prefer the tested 3.14 interpreter. No system Python packages are
changed. `uv.lock` records exact versions, registries, distributions and hashes.
Use the lock without updating it for reproduction.

From this repository root:

```sh
uv sync --frozen --cache-dir runtime/uv-cache
.venv/bin/python scripts/setup_local.py
.venv/bin/python scripts/start_dependencies.py
.venv/bin/python scripts/database_setup.py --environment development --seed
.venv/bin/python scripts/database_setup.py --environment testing --seed
.venv/bin/python scripts/provision_identity.py
.venv/bin/python scripts/run_local.py
```

The Stage 05/06 audit verifies all 53 runtime/dev packages in a clean environment.
Run `uv sync --frozen` after dependency changes. Ruff and pip-audit are locked dev
quality tools; Authlib, Flask-WTF and Requests are locked identity dependencies.

Start Docker first. The setup generator is for first use: it writes a private
ignored `.env`, replica-set keyfile and synthetic OIDC realm import; it never prints
passwords and refuses to overwrite an existing setup. A later run's nonzero exit
with “Existing .env preserved” is expected, not a request to regenerate credentials.
The dependency starter is repeatable: it preserves users/data and waits for a
writable authenticated replica set, OIDC discovery/S256 support and email capture.
If ports conflict, change this project's configuration before starting; do not stop
unrelated services. This workstation's 5000 and 8080 were occupied, so defaults
are 5050 and 8180. Use one dependency starter at a time.

## Local addresses

| Service | Loopback address | Purpose |
| --- | --- | --- |
| Flask | `http://127.0.0.1:5050/` | Public synthetic demonstration entry |
| Component gallery | `http://127.0.0.1:5050/_dev/components` | Development-only real Jinja component states |
| Student/staff shells | `http://127.0.0.1:5050/_dev/shell/student` and `/_dev/shell/staff` | Explicitly synthetic previews, no case access |
| MongoDB | `localhost:27017` | Authenticated single-node development replica set |
| OIDC | `http://127.0.0.1:8180/realms/student-support` | Isolated Keycloak realm, no public registration |
| Email capture UI/SMTP | `127.0.0.1:8025` / `127.0.0.1:1025` | Mailpit, no external relay configured |

All published dependency ports bind to `127.0.0.1`; MongoDB and identity management
interfaces are local development surfaces. SMTP capture has no production
credentials. HTTP/no local MongoDB TLS are explicit loopback-only exceptions;
not a production configuration. Do not forward these ports or use real information.

Keycloak's temporary synthetic bootstrap administrator credential is generated in
private `.env` under `OIDC_ADMIN_PASSWORD`. No working credentials are in source
control. Never paste that file into chat/logs. The local public OIDC client requires
S256 PKCE and the exact `http://127.0.0.1:5050/auth/callback` redirect. Its application
callback is implemented with verified issuer/subject mapping. No local-password
alternative exists. Synthetic accounts are provisioned explicitly using the setup
steps above; generated private credentials remain in ignored runtime storage.
See [identity/access setup](identity-access-setup.md) for the current workflow.

## Verification

```sh
.venv/bin/python -m pytest -q
RUN_RUNTIME=1 .venv/bin/python -m pytest -q
python3 scripts/check_foundation.py
python3 scripts/check_design.py
```

The first command skips the opt-in dependency test. The second requires the ready
local stack and private `.env`. It checks generic readiness, mutual credential
isolation between `student_support_dev` and `student_support_test`, and a real
aborted synthetic transaction. It does not use development credentials to write
in the test database. Never point these commands at institutional systems.

`GET /health/live` returns `{status: alive}` without dependency calls. Readiness
returns only `{status: ready}` (200) or `{status: unavailable}` (503). It checks
MongoDB replica-set primary/ping, the configured OIDC issuer/S256 discovery and
Mailpit ready endpoint. It does not disclose which dependency failed, topology,
credentials or exception details. SMTP delivery, OIDC login and case-management
acceptance are separate later-stage tests; readiness does not certify them.

Errors are generic and no-store. Invalid Host returns a minimal 400 text response
because URL generation may be unavailable. CSP excludes inline scripts/styles;
no third-party assets. No Flask client-side session fallback is provided. No
protected business endpoints are registered; guessed case/admin routes return 404.
A development gallery is never registered in testing or production configuration.

## Stop and resume

Stop the Flask runner with Ctrl-C. Stop only this project's dependency stack:

```sh
docker compose --env-file .env -f infrastructure/compose.yaml stop
```

Resume with `scripts/start_dependencies.py` and the local runner above. Named
volumes retain synthetic MongoDB/Keycloak state. Do not remove volumes or regenerate
`.env` casually: credentials and persistent state must match. A fresh reset must
explicitly identify and authorise disposal of this project's synthetic volumes;
never use a global Docker prune. The original Stage 02 prototype server, if needed,
is separate: `python3 -m http.server 8765 --bind 127.0.0.1 --directory docs/design/prototypes`.

## Production limitations

`wsgi.py` is the factory entry point; do not run a public service yet. Production
requires explicit HTTPS origins, database TLS, generated non-development secret
and a separate database name; insecure TLS overrides/debug mode fail startup.
No production secrets are loaded from `.env` by the WSGI module. These initial
checks are not complete Stage 15 hardening. Gunicorn/proxy, shared rate limiting,
detailed least-privilege collection roles, backup
recovery and institutional approvals are still pending. Local `readWrite` database
roles are scoped separately by database; Stage 07 must restrict audit/worker roles
before business features. A single node demonstrates transactions, not failover.

Stage 03 is complete; see `../evidence/stage-03-recheck/README.md` for current
results. Prior records preserve earlier failures. For isolated browser verification:

```sh
PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers .venv/bin/python -m playwright install chromium webkit
RUN_BROWSER=1 RUN_RUNTIME=1 PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers .venv/bin/python -m pytest -q
```

Playwright is a locked dev dependency; browser downloads stay ignored. Browser tests
start and stop their own loopback fixture server, use no personal browser profile,
use local dependencies and save synthetic evidence. Gallery checks block external requests. Routine screenshots default to
ignored `runtime/browser-evidence`. To record a deliberate review without overwriting
historical evidence, set `BROWSER_EVIDENCE_DIR=docs/evidence/<new-record>/browser`. Native Safari is not required.
The 29-test result verifies Stage 03 scope, not future authenticated journeys.

## Current quality checks

```sh
.venv/bin/ruff check app scripts tests wsgi.py
.venv/bin/ruff format --check app scripts tests wsgi.py
.venv/bin/python -m pip check
```

Pool size is initially 20 per application process (`MONGO_MAX_POOL_SIZE`, range
1–100) with a 1.5s connection checkout wait. Case-list queries have a 1.5s server
execution bound. Tune these only using measured workloads; these initial values
are not a production capacity claim. See `../architecture/scalability-review.md`.

Current identity/access evidence and production limitations are recorded in
`../evidence/stages-05-06/README.md`. The older 29-test result above remains historical
Stage 03 evidence; it is not the latest whole-project count.
