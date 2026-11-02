# Student Support Case Management System

A proposed secure UK university support service using Python, Flask and MongoDB.

## Current state

Stages 01–04 are complete and have passed a cleanup/dependency audit. Stage 03 provides
a local Flask runtime, shared Jinja components and isolated MongoDB/OIDC/email
capture. Stage 03 has 29 passing tests, including responsive browser checks at 390/768/1440px.
The latest audit passes all 103 unit, actual-database and browser checks from a
clean locked environment. Stage 04 includes tested contracts and synthetic fixtures. No case management or sign-in is implemented.
Use synthetic data only. No remote push or deployment has occurred.

See [local setup and verification](docs/development/local-runtime.md) and
[the completed runtime verification](docs/evidence/stage-03-recheck/README.md).

## Start here

1. Read `docs/architecture/student-support-secure-design.html`.
2. Open `docs/architecture/student-support-architecture.drawio` in draw.io.
3. Follow the master prompt and numbered stages in
   `docs/development/student-support-development-prompts.txt`.
4. Review the [requirements register](docs/requirements/register.csv),
   [open decisions](docs/decisions/open-decisions.csv),
   [prioritised backlog](docs/development/backlog.csv) and
   [delivery contract](docs/development/delivery.md).
5. Follow the sequential backlog. Stages 03/04 are verified; Stage 05 OIDC
   and server-side sessions come next. The user authorised sequential
   local stages; remote actions and real-data processing remain excluded.

See the [Stage 01–04 audit](docs/evidence/stages-01-04-audit/README.md) for cleanup,
dependency inventory, checks and scalability limits. Work is held before Stage 05
at the user's requested review checkpoint.

## Planning and evidence

- [Requirements provenance and gaps](docs/requirements/status.md)
- [Requirement/threat/test traceability](docs/testing/traceability.csv)
- [Risk register](docs/security/risk-register.csv)
- [Architecture decisions](docs/decisions/README.md)
- [Proposed layout and toolchain](docs/development/toolchain.md)
- [Stage 01 checks and limitations](docs/evidence/stage-01.md)
- [AI assistance record](docs/development/ai-use-log.md)

Run the documentation integrity check with `python3 scripts/check_foundation.py`.
It validates planning records and local design links, not application security.
Local Git history starts with the foundation commit. An origin URL is now configured;
remote history has not been verified by this implementation workflow.

## Local Python environment

```sh
uv sync --frozen --cache-dir runtime/uv-cache
.venv/bin/python scripts/setup_local.py
.venv/bin/python scripts/start_dependencies.py
.venv/bin/python scripts/run_local.py
```

Start Docker first. The first-use generator preserves existing configuration.
For the persistence setup/fixtures, follow [database setup](docs/development/database-setup.md).
Open `http://127.0.0.1:5050/`. The development-only component gallery is at
`/_dev/components`. See the setup guide for ports, stops, tests and explicit local
HTTP exceptions. Never commit the generated `.env` or runtime files.

## Layout

- `app/`: Flask factory, configuration, health, templates and development gallery;
  typed repositories and reference integrity are implemented; identity, caller
  policies and business journeys remain future work.
- `worker/`: future restricted notification worker.
- `tests/`: unit, actual-database and browser regression tests; authenticated
  feature journeys remain future work.
- `docs/`: design, requirements, decisions, risks, evidence and development log.
- `scripts/`: document checks and local setup/start commands.
- `infrastructure/`: digest-pinned local Compose dependencies and trusted bootstrap.

## Delivery discipline

Add security controls and meaningful tests with each feature. Keep design and
evidence aligned with actual behaviour. Never commit credentials, real student
data or database backups. Production readiness remains unverified and unauthorised.
