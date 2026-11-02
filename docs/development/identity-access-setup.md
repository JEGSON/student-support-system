# Local synthetic identity and access setup

Stages 05/06 use the existing loopback Docker stack. No remote push/deployment or
real student records are authorised. Run from the repository root, with Docker open:

```sh
uv sync --frozen --cache-dir runtime/uv-cache
.venv/bin/python scripts/setup_local.py
.venv/bin/python scripts/start_dependencies.py
.venv/bin/python scripts/database_setup.py --environment development --seed
.venv/bin/python scripts/database_setup.py --environment testing --seed
.venv/bin/python scripts/provision_identity.py
.venv/bin/python scripts/run_local.py
```

Visit http://127.0.0.1:5050 and choose university sign-in. Generated local credentials
are in the ignored, mode-0600 `runtime/synthetic-logins.json`. Open that file locally
to choose `student_a`, `administrator`, `approver` or a staff fixture. Never copy
its contents into evidence, Git or chat. There is no common/default password.
Provisioning uses the private local bootstrap credential; it talks only to local
Keycloak and maps synthetic subjects in the isolated dev/test databases. Reserved
`example.invalid` provider email addresses are synthetic; no email is sent.
Provisioning preserves existing passwords and roles. If provider storage is reset,
rerun explicit provisioning; recover missing private credentials deliberately rather
than enabling password fallbacks. Test callback client `support-test` permits only
http://127.0.0.1:5051/auth/callback; main client remains exact port 5050.

Student account pages expose no case journeys yet. Staff/admin/audit contexts derive
from current internal grants. `/access` is available only in a permitted admin
context; a separate `approver` must approve privileged requests. No student case
details should be entered in access reasons. Ordinary officer/triage changes use
the membership actions. Manager/audit scope requires an explicit team; global
administrator/approver requests must leave team blank. Changes revoke the target's
sessions, so sign in again to obtain updated context choices.

For a new pair of unprivileged, mapped synthetic accounts only, offline setup is:

```sh
.venv/bin/python scripts/bootstrap_access.py --environment development \
  --administrator ADMIN_USER_UUID --approver DIFFERENT_USER_UUID \
  --reason 'Explicit approved synthetic demonstration bootstrap'
```

Use actual internal UUIDs, not provider subjects. Existing seeded administrator and
approver accounts are already privileged and this command deliberately refuses to
bootstrap them again. This trusted local CLI is not reachable from the website.
Real institutional bootstrap, identity mapping and approvals remain to be designed
with the institution; this synthetic CLI refuses production databases.

Verification (requires the local dependencies and downloaded Playwright browsers):

```sh
RUN_RUNTIME=1 RUN_BROWSER=1 \
PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers \
BROWSER_EVIDENCE_DIR=runtime/browser-evidence .venv/bin/pytest -q
```

The test DB is isolated and contains only synthetic data. Test-created sessions
are labelled synthetic-v1 so explicit fixture reset can remove them without
orphaning users. Development/user sessions are not silently removed by reset;
reset refuses unlabelled dependencies. The reset regression preserves provider
subject mappings when reseeding. Do not run the fixture suite against development.

See [identity/access contract](../architecture/identity-access-contract.md) for
expiry, provider logout, concurrency and production limitations.

Stages 07/08 now provide restricted DB roles and the student submit/list/detail
journey. Follow [current setup](student-journey-setup.md) for explicit five-category
routing and the required restart; earlier stage-only absence statements above are
historical. Current case/transaction controls and evidence are linked there.
