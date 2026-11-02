# Security implementation status

The STRIDE register retains initial estimates and conditional residual targets;
none has been accepted or verified as a whole. Stage 03 adds partial infrastructure
controls relevant to T07 (body limits/generic readiness), T10 (escaping/CSP) and T11
(local authenticated replica set, generated secrets, isolation). T01 has an isolated
OIDC dependency only; application OIDC validation/session controls are Stage 05.
No role/case boundaries have yet been exposed or tested as working features.

See `../evidence/stage-03.md` for actual runtime tests and failures. Production
TLS/proxy/rate-limit/backup and least-privilege audit/worker roles remain pending.
Do not reduce risk ratings based on a passing runtime unit suite. Static synthetic
previews are not evidence of authorisation enforcement. Browser verification is
still required before the next stage. This status accompanies the preserved
baseline threat model; no new production trust boundary has been introduced.
