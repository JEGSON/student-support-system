# Run and review the student journey (Stages 07/08)

From the existing repository, with Docker open:

```sh
cd /Users/wealth/Documents/Codex/2026-11-02/go/student-support-system
uv sync --frozen --cache-dir runtime/uv-cache
.venv/bin/python scripts/start_dependencies.py
.venv/bin/python scripts/database_setup.py --environment development --seed
.venv/bin/python scripts/database_setup.py --environment testing --seed
.venv/bin/python scripts/configure_routing.py
.venv/bin/python scripts/provision_identity.py
.venv/bin/python scripts/run_local.py
```

First-time setup still requires scripts/setup_local.py before dependency startup.
For an existing Flask listener, stop/restart it in its terminal so it loads the new
code and routing. Do not start a second listener or stop unrelated services.

Open http://127.0.0.1:5050. Sign in as student_a using the private generated
credentials in ignored runtime/synthetic-logins.json. Choose student context if
needed, then Open your requests → New support request. Submit synthetic text in
one of the five support areas, record the reference and return to Your requests.
A separate student_b browser context cannot open the first student's case URL.
Sign out through Your account. Staff case work and messaging are not implemented yet.

The new dependency starter adds missing local role secrets without changing existing
passwords. It may recreate this project's MongoDB container to inject them, preserving
named volumes. Web identities now have collection roles; fixture setup uses separate
trusted maintenance credentials. Audit/worker secrets are environment-separated;
the local runner retains only allowlisted web settings in Flask config and does
not export the full .env to os.environ. The shared developer account can still
read that private file; production must isolate the app and inject only web secrets.
The full local .env is trusted setup material, not a production secret-injection model.

configure_routing.py explicitly configures all five labelled synthetic teams on first
use and preserves an existing CASE_ROUTING_JSON. Empty, missing, inactive or mismatched
routes cause safe submission failure; retry the same form after correcting routing.
Do not replace a potentially committed submission with a new form/key automatically.
No external email is sent; pending outbox entries demonstrate atomic intent only.

Run the complete local verification:

```sh
RUN_RUNTIME=1 RUN_BROWSER=1 \
PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers \
STUDENT_EVIDENCE_DIR=runtime/student-browser-evidence \
IDENTITY_EVIDENCE_DIR=runtime/identity-browser-evidence \
BROWSER_EVIDENCE_DIR=runtime/browser-evidence .venv/bin/pytest -q
```

Run only one suite against the shared synthetic test database at a time. Browser
journeys temporarily archive/restore the test student's fixtures to review empty
states and clean their own synthetic cases/audits after execution. Development
records are unaffected. The fixture reset regression preserves provider mappings;
manual explicit reset may require provisioning again. Never use real information.

See `../architecture/transaction-audit-contract.md` and
`../architecture/student-journey-contract.md` for controls and limitations.
