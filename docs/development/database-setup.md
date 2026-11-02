# Local database contracts and synthetic fixtures

Run from this repository root after the Stage 03 environment is installed:

```sh
.venv/bin/python scripts/start_dependencies.py
.venv/bin/python scripts/database_setup.py --environment development --seed
.venv/bin/python scripts/database_setup.py --environment testing --seed
RUN_RUNTIME=1 .venv/bin/python -m pytest -q
```

The starter adds a missing generated schema password to private `.env`, preserves
existing credentials and provisions a separate schema identity. On an existing
setup it may recreate only this project's MongoDB container to inject the additional
bootstrap variable; named data is preserved. First-use `setup_local.py` now generates
that secret too. Never display/share `.env` or run Compose `config` output containing
expanded environment secrets in routine evidence. Application/worker production
database-role separation is implemented in Stage 07; this full bootstrap `.env` is local only.

Schema setup accepts only development/testing environments, installs 16 contracts
and named indexes, and exits with a generic failure on errors. Read the schema
upgrade procedure in `../architecture/persistence-contract.md` before any change.
No application routes, identity callbacks or case services are exposed by setup.

## Fixture version synthetic-v1

30 idempotent documents: 12 user records, five teams, six memberships, four cases,
one student-visible message, one distinct internal note and one worker principal.
Covers students A/B; finance/disability; assigned, unassigned same-team and unrelated
team officers; scoped managers; triage; administrator; approver; reviewer; disabled
account and notification worker. All names/references/content are explicitly
synthetic. No passwords, tokens or real contact records are in fixture source.

User issuer/subjects are **synthetic placeholder mappings**, not verified identities
or usable OIDC login accounts. Stage 05 must explicitly provision provider accounts
and map verified subjects; do not accept arbitrary role claims or silently enable a
password fallback. The separate inline design gallery is not a view of this database.
OIDC login and the student journey are implemented; see `student-journey-setup.md`
for provisioning and explicit five-category routing. Staff case work remains later.

Seeding uses deterministic IDs and transactional setOnInsert: repeat execution
preserves existing fixture records rather than silently resetting role/content
changes. Timestamps in fixtures are fixed UTC test instants; no live metric claim.
`SYNTHETIC_NOTE_NEVER_STUDENT` is a distinctive future non-disclosure fixture.

## Explicit fixture reset

For a deliberately disposable isolated synthetic setup, the operator can request:

```sh
.venv/bin/python scripts/database_setup.py --environment testing --reset-synthetic --seed
```

This is an explicit reset action, not a startup default. It deletes only records
labelled synthetic-v1 in a transaction and reseeds when requested. It preserves
unlabelled records and refuses reset if they reference fixture records, preventing
obvious orphaned service references/audit targets. It does not drop databases or
collections. The same flag can target development only when the operator intends
to reset that synthetic fixture; do not run it over work you intend to retain.
This is not a general retention/disposal feature. Real policy durations stay unset.

Session/submission TTL cleanup is not an expiry-access check. Cases and claims have
no automatic TTL disposal. Stage 05/06/09 enforce their access/expiry rules; Stage 13
implements reviewed lifecycle controls. Test results are in `../evidence/stage-04.md`.

Stage 07 setup uses support_fixture for offline development writes and support_test
for isolated test maintenance. Public web identities cannot read/update/delete
audits or delete history. See `../architecture/transaction-audit-contract.md` for
restricted environment-separated audit/worker roles and privileged operator risks.
