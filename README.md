# Student Support Case Management System

A proposed secure UK university support service using Python, Flask and MongoDB.

## Current state

Stage 01: repository and planning foundation complete. The application, dependencies, identity provider,
database runtime and automated tests have not been implemented. No server can
be started yet. Use synthetic data throughout development.

## Start here

1. Read `docs/architecture/student-support-secure-design.html`.
2. Open `docs/architecture/student-support-architecture.drawio` in draw.io.
3. Follow the master prompt and numbered stages in
   `docs/development/student-support-development-prompts.txt`.
4. Review the [requirements register](docs/requirements/register.csv),
   [open decisions](docs/decisions/open-decisions.csv),
   [prioritised backlog](docs/development/backlog.csv) and
   [delivery contract](docs/development/delivery.md).
5. Next: Prompt 02 visual design. Each stage needs separate authorisation.

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
Local Git history starts with the foundation commit; no GitHub remote is configured.

## Local Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Dependency versions and installation commands will be established during the
runtime stage. `.env.example` contains proposed configuration names; copy it
to `.env` only when configuring the implemented runtime and replace every
placeholder. Keep `.env` private.

## Layout

- `app/`: future Flask modules, policies, services, repositories and UI.
- `worker/`: future restricted notification worker.
- `tests/`: future unit, integration, browser and security tests.
- `docs/`: design, requirements, decisions, risks, evidence and development log.
- `scripts/`: future setup and maintenance commands.
- `infrastructure/`: future isolated local and deployment configuration.

## Delivery discipline

Add security controls and meaningful tests with each feature. Keep design and
evidence aligned with actual behaviour. Never commit credentials, real student
data or database backups. Do not describe this scaffold as production-ready.
