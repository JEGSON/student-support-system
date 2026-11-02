# Student Support Case Management System

Python/Flask/MongoDB university support demonstration. Stages 01–19 are delivered
for local synthetic testing: student requests, scoped staff work, conversation and
internal notes, lifecycle, referrals, generic captured notifications, access controls,
retention framework and isolated encrypted recovery. Production deployment,
real student data and external email remain excluded. The user separately authorised
publishing the source and local development history to the configured GitHub repository.

Start with [the testing checklist](docs/handbook/testing-checklist.md),
[setup](docs/handbook/setup.md) and [student/staff guide](docs/handbook/user-guide.md).
Restart an existing server to load the latest code.

```sh
cd /Users/wealth/Documents/Codex/2026-11-02/go/student-support-system
.venv/bin/python scripts/run_local.py
```

Open http://127.0.0.1:5050. Choose **Create a student account** to register with
synthetic details, then **Your profile** to edit your preferred name/course.
Docker dependencies must already be running. For a new
installation follow setup, including frozen dependency sync, private configuration,
database contracts/routing and synthetic identity provisioning. Generated passwords
are in ignored runtime/synthetic-logins.json; none are committed or packaged.

See [handover](docs/handbook/handover.md), [operations](docs/handbook/operations.md),
[known limitations](docs/handbook/known-limitations.md), [as-built architecture](docs/architecture/runtime-status.md),
[editable overview](docs/architecture/architecture-overview.html),
[requirements](docs/requirements/register.csv), [traceability](docs/testing/traceability.csv),
[risks](docs/security/risk-register.csv), [integrated evidence](docs/evidence/stage-16/README.md)
and [AI-use statement](docs/AI-USE-STATEMENT.md).

The original design HTML and stage contracts preserve historical decisions; current
runtime/inventory/runbooks reconcile implementation. The full assessment rubric and
institutional AI policy remain missing. FR-04/06 and live-service institutional
policies are unresolved. Automated accessibility checks do not certify WCAG AA.

Source is in app/, worker/, scripts/ and infrastructure/. Tests include unit, real
replica-set integration and isolated Chromium/WebKit journeys. Run documentation
checks with `.venv/bin/python scripts/check_foundation.py` and
`.venv/bin/python scripts/check_design.py`. Full runtime commands are in setup.

Local Git history records incremental development. An origin is configured; remote
publication/history has not been verified. The assessment ZIP excludes Git metadata;
review history in this repository. Package and extraction checks are documented in
[the release checklist](docs/handbook/release-checklist.md).

Student registration and editable profiles were added after the initial handover.
See [the account/profile contract](docs/architecture/account-profile-contract.md) and
[feature evidence](docs/evidence/account-profiles/README.md). Staff/administrator
access remains controlled; production self-registration is forbidden by config.
