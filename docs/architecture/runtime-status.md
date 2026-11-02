# Target architecture versus implemented runtime

2 November 2026, Stages 07/08 implemented. The v1.0 HTML and draw.io remain the preserved
proposed baseline, not an as-built or production claim. No change to trust boundaries
or demonstration access rules is authorised by a layout preview.

| Decision | Implemented now | Still pending |
| --- | --- | --- |
| ADR-01 | Flask application factory; separate configuration/health/gallery modules | Staff work/communication/referrals (09 onward) |
| ADR-02 | Jinja base/components, local CSS, synthetic development shells | Student, account and access pages reviewed at 390/768/1440 |
| ADR-03 | Snapshot/majority transactions; version/revocation guards; append-only audit DB grants; atomic submission | Full lifecycle/outbox-feature coverage; current 16 validators/index sets verified |
| ADR-04/05 | Authlib OIDC/S256; issuer/subject mapping; opaque hashed Mongo sessions and CSRF; explicit context | Production provider/MFA integration; operational hardening (15) |
| ADR-06 | Generic transactional outbox and lease/retry/dead states; restricted worker DB identities | Email rendering/delivery/contact policy and operational alerts (11) |
| ADR-07 | Loopback local runner; initial host/header/body/error controls | Gunicorn/HTTPS edge/proxy and operational verification (15) |
| ADR-08/09 | Generated ignored local secrets; image digests and dependency lock; local database separation | Production encryption, backups, recovery, CI and institutional operation |

Local ports: Flask 5050, identity 8180→container 8080, MongoDB 27017, Mailpit
8025/1025. None is a public endpoint. An origin URL is now configured locally; remote history
has not been verified and no deployment is claimed.

Current evidence: `../evidence/stage-07/README.md` and `../evidence/stage-08/README.md`.
Student submission/tracking, current role/session/admin and atomic persistence
checks are executable. Later case-work/lifecycle/operational coverage remains pending.

Current data contracts and additions are in `persistence-contract.md`.
`identity-access-contract.md` preserves the Stage 05/06 checkpoint;
`transaction-audit-contract.md` and `student-journey-contract.md` define current
behaviour. Student case endpoints now exist. Staff/communication endpoints remain
absent. The preserved draw.io topology still applies; no trust boundary changed.
