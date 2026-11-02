# Stage 15 operational preparation

244 unit/integration checks passed in 10.77s. Exact one-hop trusted-proxy validation, HTTPS/HSTS production gate, shared Mongo fixed-window limits and fail-closed limit storage, metadata-only Gunicorn logs, restricted role isolation and quarantined encrypted recovery are implemented. Recovery test measured a small synthetic snapshot/restore with disposal-after-snapshot replay, session invalidation and notification suppression; recovery-small.json records actual values.

Gunicorn 26.2.0 is locked; template binds loopback with two eight-thread workers, no preload/debugger and bounded requests/timeouts. No public deployment occurred. Fernet/cryptography 50.0.2 authenticates and encrypts snapshots; local key file is separate/0600, but true KMS/operator separation and institutional hosting approval remain production gates. Restore refuses nonempty/normal app DBs and requires a current authenticated external disposal ledger. A partial restore stays quarantined; restart from a deliberately cleared quarantine or reapply the ledger before activation. Replication is not backup.

Primary docs: https://gunicorn.org/reference/settings/ and https://cryptography.io/en/stable/fernet/.
