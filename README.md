# Student Support Case Management System

A proposed secure UK university support service using Python, Flask and MongoDB.

## Current state

Stage 01 foundation and Stage 02 visual specification are committed. Stage 03 now
has a local Flask runtime, shared Jinja components and isolated MongoDB/OIDC/email
capture. All 17 runtime tests pass. Stage 03 remains incomplete pending rendered
responsive browser verification; no case management or sign-in is implemented.
Use synthetic data only. No remote push or deployment has occurred.

See [local setup and verification](docs/development/local-runtime.md) and
[the runtime evidence/remaining gate](docs/evidence/stage-03.md).

## Start here

1. Read `docs/architecture/student-support-secure-design.html`.
2. Open `docs/architecture/student-support-architecture.drawio` in draw.io.
3. Follow the master prompt and numbered stages in
   `docs/development/student-support-development-prompts.txt`.
4. Review the [requirements register](docs/requirements/register.csv),
   [open decisions](docs/decisions/open-decisions.csv),
   [prioritised backlog](docs/development/backlog.csv) and
   [delivery contract](docs/development/delivery.md).
5. Follow the sequential backlog. Stage 03 responsive verification is the current
   gate; do not start Stage 04 before it is resolved. The user authorised sequential
   local stages; remote actions and real-data processing remain excluded.

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
Open `http://127.0.0.1:5050/`. The development-only component gallery is at
`/_dev/components`. See the setup guide for ports, stops, tests and explicit local
HTTP exceptions. Never commit the generated `.env` or runtime files.

## Layout

- `app/`: Flask factory, configuration, health, templates and development gallery;
  business policies/services/repositories remain future work.
- `worker/`: future restricted notification worker.
- `tests/`: runtime unit and opt-in actual dependency tests; feature/browser tests pending.
- `docs/`: design, requirements, decisions, risks, evidence and development log.
- `scripts/`: document checks and local setup/start commands.
- `infrastructure/`: digest-pinned local Compose dependencies and trusted bootstrap.

## Delivery discipline

Add security controls and meaningful tests with each feature. Keep design and
evidence aligned with actual behaviour. Never commit credentials, real student
data or database backups. Production readiness remains unverified and unauthorised.
