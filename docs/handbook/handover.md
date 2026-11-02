# Handover and next-release plan

The local synthetic assessment implementation is delivered through Stage 19. The
full rubric/submission/AI-policy requirements are unavailable, so assessment
conformity is provisional. Live operation is unauthorised and requires further work.

| Objective | Status and practical consequence | Proposed owner |
| --- | --- | --- |
| Core student/staff case journey | Met locally: ownership, scoped work, messages/notes, lifecycle and conflicts | Application/service owner |
| Referrals and generic notifications | Met locally: selected sharing, separate case, bounded local retries; no real mail | Service/privacy and mail owner |
| Access administration/audit | Partial: controlled grants, durable audits, scoped offline reader; no reviewer dashboard/archived forensic procedure | Access/security owner |
| Retention/recovery | Partial: synthetic holds/disposal, encrypted quarantine/replay; no real schedule/offsite custody/daily cadence | Privacy/operations owner |
| Performance/security evaluation | Observed targets met locally; one GET503, narrower student-only workload and single workstation limit conclusions | Engineering/operations |
| Accessibility | Partial: responsive real browsers, axe/keyboard/reflow; human screen-reader/native zoom review pending | Accessibility/service owner |
| Assessment constraints | Python/Flask/MongoDB, SSDLC, tests/docs/AI disclosure delivered; full rubric and FR-04/06 unresolved | Student/assessor |
| GitHub history | Local meaningful commits; configured origin only, remote publication unverified/no push | Repository owner |
| Production policies | Blocked: identity/MFA, privacy grounds, retention, safeguarding, hosting/on-call and KMS approvals absent | Institutional owners in open-decisions.csv |
| Attachments/migration/integrations | Deferred by agreed scope; no implied authorisation | Sponsor/privacy/security |

Risk register T01–T12 records controls/evidence and unaccepted residual targets.
No risk is accepted on behalf of the university. Missing policies block real data;
privileged operators can still defeat app-level restrictions, human referral text
can overshare, at-least-once mail can duplicate and stale disposal ledgers threaten
restoration. Keep the service local until owners resolve these consequences.

## Operating responsibilities

Access owner reviews membership/privilege grants, separate approval and departures;
managers reassign active work and preserve attribution. Service owner supplies
response/urgent-help wording and routes safeguarding concerns under an approved
procedure. Security owner reviews audit/denial metadata, incidents and privileged
operators. Operations owns dependencies/images, vulnerability review, monitoring,
outbox-age/dead alerts, secrets, backups, offsite key/ledger custody and periodic
restore exercises. Privacy owner supplies holds, retention/backup expiry and lawful
sharing decisions. Schedule reviews and name real accountable people before launch.
The app makes no automated risk/eligibility or emergency intervention decision.

## Demonstration sequence

Follow testing-checklist.md for the finance journey, note separation, question/reply,
outcome/reopen and access denials. Then demonstrate accommodation → wellbeing and
disability → academic with minimal summary, source approval and separate target case.
Use the private generated accounts; never insert real student records.

For a repeatable notification failure/control demonstration without stopping any
shared service, run against the synthetic test database:

```sh
RUN_RUNTIME=1 .venv/bin/pytest -q tests/integration/test_delivery.py
RUN_RUNTIME=1 .venv/bin/pytest -q tests/integration/test_lifecycle.py tests/integration/test_operations.py
```

The delivery tests simulate SMTP outage/crash-after-send, prove bounded retries,
show generic capture and keep the case transaction intact. Lifecycle/recovery tests
backdate synthetic cases, exercise holds/independent disposal and replay the ledger
in quarantine. Verify exact test file names in tests/integration if extending tests.
The operations runbook documents manual local commands and remaining operator gates.

## Prioritised next release

1. Resolve rubric/FR-04/06 and AI disclosure format; name service/privacy/access/security/
   operations owners; approve identity/MFA, sharing, safeguarding, retention and hosting.
2. Complete independent security review and human accessibility/user testing; review
   archived/disposed forensic access and a minimal audited reviewer interface if authorised.
3. Trace/reproduce the workload GET503 on dedicated hardware; measure staff/referral/
   admin load, larger payloads and bounded-list navigation. Set actual demand targets.
4. Design real HTTPS edge, secret injection/KMS, storage encryption, HA, protected audit
   copy and offsite backup/key/ledger custody; prove backup cadence and restore operations.
5. Only with new approval: attachments (malware/content isolation), migration (mapping/
   consent/quality), student-record and mail integrations (identity/provenance/minimisation).
   Each requires renewed privacy/threat modelling and acceptance tests before implementation.

No push, upload, production deployment or external contact has been performed.
