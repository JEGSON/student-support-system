# Local setup and verification

Use only synthetic information. The application is a local demonstration, not an
approved university service. Python 3.14.7, uv 0.11.3, Docker Compose and Node (for
optional accessibility tooling) were used on macOS. Python 3.13 is permitted by
metadata but was not independently tested.

From the repository root:

```sh
uv sync --frozen --cache-dir runtime/uv-cache
.venv/bin/python scripts/setup_local.py
.venv/bin/python scripts/start_dependencies.py
.venv/bin/python scripts/database_setup.py --environment development --seed
.venv/bin/python scripts/database_setup.py --environment testing --seed
.venv/bin/python scripts/configure_routing.py
.venv/bin/python scripts/provision_identity.py
.venv/bin/python -m scripts.configure_portals
.venv/bin/python scripts/run_local.py
```

On an existing installation skip setup_local.py; its “Existing .env preserved”
exit is intentional. The dependency starter preserves volumes/passwords and adds
missing local role secrets. Do not delete volumes or overwrite .env to resolve
credential mismatches. Stop/restart an existing Flask terminal after source/config
changes; do not launch a second listener on 5050 or stop unrelated services.

Open http://127.0.0.1:5050 for students and http://localhost:5050 for staff. Keep
these hostnames distinct: changing only the port does not isolate browser cookies.
Existing installations should run the dependency starter to mount the portal login
theme, then `.venv/bin/python -m scripts.configure_portals`. This preserves existing
accounts/passwords, installs four exact local/test callback clients, and assigns
the portal-specific identity theme. It automatically advances through Keycloak's
native fresh-account action when an identity is remembered, without global logout.
The theme requires JavaScript for this convenience; Keycloak's manual account
selection remains available when JavaScript is disabled.

After updating source, apply the current validators without reseeding records:
`.venv/bin/python scripts/database_setup.py --environment development` and the
same command with `--environment testing`. The codebase review added an optional
audit-purpose field used by controlled archive/audit reads. Restart the runner
after applying validators. Existing staff/admin accounts sign in directly; only
new service access needs an invitation and a matching verified provider account.

Generated credentials for 17 synthetic accounts are
private in runtime/synthetic-logins.json (0600), excluded from Git/package. There
is no shared/default password. Account labels and flows are in user-guide.md.
The provisioning command also configures local student registration. Continue to
use reserved @example.invalid addresses for local testing. The portal configurator
removes the provider's demo-only email-field hint while preserving the reserved
email-domain restriction. On an existing seeded installation you may run
`.venv/bin/python scripts/configure_registration.py` to configure only registration
without remapping fixture identities. Restart the app afterwards. SELF_REGISTRATION_ENABLED
defaults to 0 and can only be enabled with the exact synthetic provider; it is
forbidden in production. New student passwords are chosen on the provider page,
not written into synthetic-logins.json. Profile changes live in the application.

Local addresses: Keycloak 8180, MongoDB 27017, Mailpit UI 8025/SMTP 1025. All bind
127.0.0.1. No real external email is enabled. Worker in a separate terminal:

```sh
.venv/bin/python scripts/run_worker.py --environment development
```

Use --once for one job and backlog/dead counts. Ctrl-C stops the worker. Never
change its SMTP origin/contact restrictions to send real email without review.

Verification:

```sh
PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers .venv/bin/python -m playwright install chromium webkit
npm install --prefix runtime/accessibility axe-core@4.14.0 --ignore-scripts --no-audit --no-fund
RUN_RUNTIME=1 RUN_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers \
STUDENT_EVIDENCE_DIR=runtime/student-browser-evidence \
IDENTITY_EVIDENCE_DIR=runtime/identity-browser-evidence \
BROWSER_EVIDENCE_DIR=runtime/browser-evidence .venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python scripts/check_foundation.py
.venv/bin/python scripts/check_design.py
```

Run one suite/workload at a time against the shared test DB. Tests may explicitly
reset labelled test fixtures and restore mappings; they do not operate on dev.
Browser complete-case evidence intentionally writes docs/evidence/stage-14; other
browser destinations are configurable and default to ignored runtime. No personal
browser profile is used. Unit-only checks run with `.venv/bin/pytest tests/unit`.

Frozen dependencies/hashes are in uv.lock. The encrypted evaluation snapshots,
credentials, virtual environments and captured messages are not submission source.
The extracted-package check covers a fresh hash-checked environment and unit/docs
checks; the full local Docker/browser run was verified in the retained checkout.
