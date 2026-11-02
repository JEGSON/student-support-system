# Target architecture versus implemented runtime

2 November 2026, Stage 04 completed. The v1.0 HTML and draw.io remain the preserved
proposed baseline, not an as-built or production claim. No change to trust boundaries
or demonstration access rules is authorised by a layout preview.

| Decision | Implemented now | Still pending |
| --- | --- | --- |
| ADR-01 | Flask application factory; separate configuration/health/gallery modules | Business service/repository modules |
| ADR-02 | Jinja base/components, local CSS, synthetic development shells | Authenticated feature pages (runtime shells reviewed at 390/768/1440) |
| ADR-03 | Authenticated local replica set, separate dev/test identities, real aborted-transaction check | Transaction coordinator/audit policy (07); 15 validators/index sets and fixture integrity checks implemented (04) |
| ADR-04/05 | Isolated OIDC provider/PKCE-required public client; no client-session fallback | OIDC login, verified mapping, opaque hashed server sessions (05) |
| ADR-06 | Local email capture only | Worker/outbox processing and scoped identity (07/11) |
| ADR-07 | Loopback local runner; initial host/header/body/error controls | Gunicorn/HTTPS edge/proxy and operational verification (15) |
| ADR-08/09 | Generated ignored local secrets; image digests and dependency lock; local database separation | Production encryption, backups, recovery, CI and institutional operation |

Local ports: Flask 5050, identity 8180→container 8080, MongoDB 27017, Mailpit
8025/1025. None is a public endpoint. An origin URL is now configured locally; remote history
has not been verified and no deployment is claimed.

Current scoped evidence: `../evidence/stage-03-recheck/README.md` (29 tests and
responsive screenshots). Full feature accessibility/security remains future work.

Stage 04 data-model additions and actual constraints are in `persistence-contract.md`;
its observed tests are in `../evidence/stage-04.md`. No authenticated business endpoint
exists yet. The v1.0 design artefacts remain the preserved proposal.
