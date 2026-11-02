# Student Support Case Management System

A proposed secure UK university support service using Python, Flask and MongoDB.

## Current state

Stages 01–06 are implemented locally: the Flask/Jinja runtime, MongoDB contracts,
real Keycloak OIDC/PKCE sign-in, opaque server sessions, context selection, central
relationship policies and metadata-only access administration. Case submission and
case-management pages begin after the Stage 07 transaction/audit foundation.
The full clean-environment suite passes 190 checks, including real provider login
and browser review. Use synthetic data only. No remote push or deployment has occurred.

See [identity/access setup](docs/development/identity-access-setup.md),
[implementation contract](docs/architecture/identity-access-contract.md) and
[verification evidence](docs/evidence/stages-05-06/README.md).

## Start here

1. Read `docs/architecture/student-support-secure-design.html`.
2. Open `docs/architecture/student-support-architecture.drawio` in draw.io.
3. Follow the master prompt and numbered stages in
   `docs/development/student-support-development-prompts.txt`.
4. Review the [requirements register](docs/requirements/register.csv),
   [open decisions](docs/decisions/open-decisions.csv),
   [prioritised backlog](docs/development/backlog.csv) and
   [delivery contract](docs/development/delivery.md).
5. Follow the sequential backlog. The user authorised Stages 05/06; Stage 07
   requires the next instruction. Production, real-data and remote actions remain excluded.

The [Stage 01–04 audit](docs/evidence/stages-01-04-audit/README.md) preserves the
previous checkpoint and foundation scalability review.

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
.venv/bin/python scripts/database_setup.py --environment development --seed
.venv/bin/python scripts/database_setup.py --environment testing --seed
.venv/bin/python scripts/provision_identity.py
.venv/bin/python scripts/run_local.py
```

Start Docker first. The first-use generator preserves existing configuration.
For the persistence setup/fixtures, follow [database setup](docs/development/database-setup.md).
Open `http://127.0.0.1:5050/`. The development-only component gallery is at
`/_dev/components`. See the setup guide for ports, stops, tests and explicit local
HTTP exceptions. Never commit the generated `.env` or runtime files.

## Layout

- `app/`: Flask factory, configuration, health, templates and development gallery;
  typed repositories, OIDC/sessions and central policies; case journeys remain later work.
- `worker/`: future restricted notification worker.
- `tests/`: unit, actual-database and browser regression tests; authenticated
  student/admin sign-in journeys are verified; case journeys remain future work.
- `docs/`: design, requirements, decisions, risks, evidence and development log.
- `scripts/`: document checks and local setup/start commands.
- `infrastructure/`: digest-pinned local Compose dependencies and trusted bootstrap.

## Delivery discipline

Add security controls and meaningful tests with each feature. Keep design and
evidence aligned with actual behaviour. Never commit credentials, real student
data or database backups. Production readiness remains unverified and unauthorised.
