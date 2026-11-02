# Target architecture versus implemented runtime

2 November 2026, Stages 05/06 implemented. The v1.0 HTML and draw.io remain the preserved
proposed baseline, not an as-built or production claim. No change to trust boundaries
or demonstration access rules is authorised by a layout preview.

| Decision | Implemented now | Still pending |
| --- | --- | --- |
| ADR-01 | Flask application factory; separate configuration/health/gallery modules | Case journey services (08 onward) |
| ADR-02 | Jinja base/components, local CSS, synthetic development shells | Case pages; account/access pages reviewed at 390/768/1440 |
| ADR-03 | Authenticated local replica set, separate dev/test identities, real aborted-transaction check | Transaction coordinator/audit policy (07); 16 validators/index sets and fixture integrity checks implemented (04) |
| ADR-04/05 | Authlib OIDC/S256; issuer/subject mapping; opaque hashed Mongo sessions and CSRF; explicit context | Production provider/MFA integration; operational hardening (15) |
| ADR-06 | Local email capture only | Worker/outbox processing and scoped identity (07/11) |
| ADR-07 | Loopback local runner; initial host/header/body/error controls | Gunicorn/HTTPS edge/proxy and operational verification (15) |
| ADR-08/09 | Generated ignored local secrets; image digests and dependency lock; local database separation | Production encryption, backups, recovery, CI and institutional operation |

Local ports: Flask 5050, identity 8180→container 8080, MongoDB 27017, Mailpit
8025/1025. None is a public endpoint. An origin URL is now configured locally; remote history
has not been verified and no deployment is claimed.

Current scoped evidence: `../evidence/stages-05-06/README.md`. Core role, session,
context and administration checks are executable; full case-feature and production
accessibility/security verification remains later work.

Stage 04 data contracts plus Stage 05/06 additions are in `persistence-contract.md`.
`identity-access-contract.md` records exact current identity/access behaviour and
concurrency semantics. Account and access endpoints exist; case endpoints remain
absent. The preserved draw.io topology remains applicable; no trust boundary changed.
