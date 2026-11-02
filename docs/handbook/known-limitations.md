# Known limitations and gates

- Synthetic demonstration only. Privacy grounds, DPIA, retention schedule, urgent-help
  wording, operating hours, identity/MFA, access owners, hosting and production KMS/
  on-call approvals remain OD-02–07; no live data/service is authorised.
- Full assessment rubric, inaccessible original attachment, deadline and institutional
  AI policy remain missing (OD-01). FR-04/06 are undefined. Assessment conformity cannot
  be certified. Local Git history is real. Source publication to the configured GitHub origin
  is now separately authorised; the initial handover excluded that action.
  Production deployment remains outside this authorisation.
- Axe/browser/keyboarding/large-text checks do not certify WCAG 2.2 AA. Native screen-
  reader and complete manual zoom/usability review still require a human reviewer.
- Audit read is an explicit offline scoped service, not a public dashboard/export.
  Archived/disposed forensic review needs a reviewed operator procedure. Audit and
  disposal metadata resist ordinary web mutation but privileged infrastructure and
  collusion remain risks; no immutable external audit sink/KMS is implemented.
- Local SMTP capture only, reserved contacts and at-least-once delivery. Stable
  Message-ID does not guarantee provider deduplication. Production contact provenance,
  mail ownership and alert routing remain unconfigured.
- Workload was all student read/message paths with small synthetic payloads and
  preissued test sessions; OIDC/SMTP latency, staff/referral load, HA/failover and
  production traffic excluded. One GET 503 occurred; cause unconfirmed. Schema/fixture
  maintenance/probes ran on the same workstation. Do not generalise p95 to capacity.
- Single-node replica set is not HA. Recovery measurements are synthetic, not proof
  of daily/off-site backup cadence or real RPO. Expanded backup JSON is capped at
  200 MiB and uses bounded memory; larger deployments need an approved backup design.
- Staff queues use bounded pages; referral/retention/admin lists are bounded (100,
  source referral scope lookup 1,000) with limited navigation/search. Large-scale
  administration and staff-role workload require further evaluation before live use.
- Uploaded attachments, exports, historical migration, student-record integration,
  automatic risk scoring, emergency break-glass and offline interaction remain excluded.
- Local setup assumes documented loopback ports and one shared Docker project; do not
  run two different secret sets against its existing named volumes. Extraction review
  uses isolated dependencies/unit/docs checks, not a second live deployment.
