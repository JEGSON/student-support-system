# Target architecture versus implemented runtime

2 November 2026, Stage 03 checkpoint. The v1.0 HTML and draw.io remain the preserved
proposed baseline, not an as-built or production claim. No change to trust boundaries
or demonstration access rules is authorised by a layout preview.

| Decision | Implemented now | Still pending |
| --- | --- | --- |
| ADR-01 | Flask application factory; separate configuration/health/gallery modules | Business service/repository modules |
| ADR-02 | Jinja base/components, local CSS, synthetic development shells | Authenticated feature pages and rendered responsive review |
| ADR-03 | Authenticated local replica set, separate dev/test identities, real aborted-transaction check | Validators/indexes (04), transaction coordinator/audit policy (07) |
| ADR-04/05 | Isolated OIDC provider/PKCE-required public client; no client-session fallback | OIDC login, verified mapping, opaque hashed server sessions (05) |
| ADR-06 | Local email capture only | Worker/outbox processing and scoped identity (07/11) |
| ADR-07 | Loopback local runner; initial host/header/body/error controls | Gunicorn/HTTPS edge/proxy and operational verification (15) |
| ADR-08/09 | Generated ignored local secrets; image digests and dependency lock; local database separation | Production encryption, backups, recovery, CI and institutional operation |

Local ports: Flask 5050, identity 8180→container 8080, MongoDB 27017, Mailpit
8025/1025. None is a public endpoint. No GitHub remote/deployment exists.
