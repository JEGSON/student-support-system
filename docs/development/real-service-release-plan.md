# Single-university real-service release plan

Implementation checkpoint: the configurable release now implements the next coding
increment. See [operator guide](../handbook/real-service-setup.md) and
[release evidence](../evidence/real-service/README.md). The plan below remains the
original scope; external services, complete-erasure expiry/re-registration operations,
invitation-email automation and independent assurance remain explicitly limited in
the guide. No production launch is claimed.

3 November 2026. The user requests real user/account/database functionality,
including creating and deleting profiles. The user selected a single university
as the operating model and acts as the initial service operator. This is a design
assumption for this release, not evidence that an institution has approved policies
or connected its identity infrastructure. The existing Flask/MongoDB architecture
and scoped case/referral model are retained. No multi-university tenancy is added.

This document records the proposed next implementation release. It does not claim
that real registration, account erasure, public hosting or external email are now
enabled. No real records, provider secrets, deployment or paid resources were used
in preparing this plan. The currently running local environment remains isolated.

## Current implementation and changes needed

| Area | Already implemented | Required next change |
| --- | --- | --- |
| Data persistence | Actual authenticated MongoDB, transactions, indexes and scoped services | Separate production replica set, TLS/private access, encryption, secrets and verified recovery |
| Identity | OIDC/PKCE and validated local Keycloak identities | Production identity configuration and explicit institution-approved enrolment rules; no automatic trust in email domains/role claims |
| Registration | Synthetic student enrolment and generated demo identifiers/contact | Verified real contact and student eligibility; real reference from trusted source or clearly separate application reference |
| Own profile | Preferred name/course editing, CSRF, audit and version guard | Complete the approved profile fields and verified contact-change lifecycle; no self-editable roles or official student identity |
| Account deletion | Administrator disablement and case-level synthetic disposal | Self-service account closure and policy-driven personal-data erasure across linked systems |
| School staff | Scoped manager/officer roles, independent grants, queue/replies | Controlled staff invitations/provisioning and a usable service/team administration flow; privileged MFA and named owners |
| Notifications | Transactional generic jobs, retries, local capture | Verified real recipients, authenticated production delivery, preferences where appropriate, bounce/failure monitoring and privacy-safe templates |
| Case work | Five support areas, assignment/start/messages/notes/closure/referrals | Real team ownership, staffing and approved response/urgent-help wording; delivery status and operational follow-up |
| Operations | Gunicorn/proxy/rate-limit preparation and local encrypted recovery | Hosted HTTPS service, protected identity service, separate worker, managed restarts, monitoring/on-call, offsite backup and restore exercises |
| Assurance | Previous integrated 301 checks and subsequent scoped staff-entry 139 checks | New account/privacy tests, independent security and human accessibility review, dedicated workload/restore evaluation before launch |

## Identity, registration and staff onboarding

Prefer the university's approved OIDC service when available. If unavailable, keep
credentials in a separately operated production identity provider and support
verified email plus an approved student eligibility/invitation process. Verifying
an email address alone does not prove university membership. The exact provider,
claims, domain, credentials and eligibility source remain deployment inputs.

The application will explicitly distinguish pending verification/enrolment from
active access. Expiring one-use verification/invitation links, resend throttling,
password reset/recovery and safe contact-change flows belong in this release.
Never put privileged identity-provider credentials in the web app or public code.
Production registration must use a reviewed enrolment policy rather than removing
the current local-issuer check. Existing student accounts must never acquire staff
permissions from submitted form fields or unchecked provider claims.

The operator bootstraps a named administrator securely; independent access approval
remains required for privileged roles. Staff invitations are bound to an intended
identity, team, role and expiry. The existing support manager/officer scopes continue
to govern case reads and replies; administrator status alone does not grant case
narrative access. Every advertised support area needs an accountable staffed team.

## Profile creation, closure and deletion contract to implement

The website will expose profile creation/view/edit and a clearly labelled account-
closure/deletion flow. Profile deletion is not an unconditional cases.delete_many
or an account_status change presented as completed erasure.

1. Re-authenticate before closure/deletion, protect the POST with CSRF, show what
   access will end, explain any retained records and require explicit confirmation.
2. Close platform access immediately on confirmed closure: invalidate all sessions,
   stop new requests/messages, suppress queued notifications and arrange staff
   reassignment if the closing account holds staff responsibilities. Do not silently
   mark outstanding student cases as resolved.
3. Record a minimal durable erasure request with an honest state, for example
   requested/review-required/processing/completed/partially-retained/failed.
4. If nothing requires retention, erase unnecessary profile/contact/verification
   data and the platform-owned identity through an idempotent controlled worker.
   A university SSO account is outside this application: closing platform access
   must not delete the person's university-wide account.
5. For cases, notes, messages, referrals and attribution, apply the approved record-
   by-record retention/erasure decision. Preserve required evidence only with a
   documented purpose/access limit/retention duration. Maintain referential integrity
   through an explicit closed-principal/pseudonymous attribution design where
   justified, rather than leaving dangling user references. Pseudonymised retained
   information is still personal data when it can be linked to a person.
6. Extend the disposal ledger/recovery process to cover account erasure, verification
   data, pending mail, identity-provider changes, approved exports/processors and
   backup expiry. Restore reconciliation must not resurrect deleted profiles,
   active sessions or old notifications. Minimal anti-recreation records and any
   later re-registration must follow an explicit retention/enrolment policy.
7. Show the user completion or a specific retained-data explanation; do not describe
   queued/failed/partially retained erasure as permanent complete deletion. External
   identity/provider actions cannot share a MongoDB transaction, so use durable
   retryable jobs, strict worker privileges and recovery reconciliation.

Optional profile fields can be cleared without closing the account. The account
closure/erasure screen must make that distinction clear. Actual retention durations,
legal holds, ongoing cases and staff-record obligations require the service/privacy
owner's decisions before the real erasure executor is enabled.

## Privacy and service governance

Identify the accountable operating organisation, processing purposes, privacy
contact, data processors, recipients, approved retention schedule and locations/
transfer arrangements. Collect only fields needed for support; DOB, home address,
ID documents and extra sensitive fields are not added by default. Keep marketing
choices separate from service notices and do not assume a consent checkbox resolves
all lawful-basis questions.

Wellbeing/disability requests may contain health data. Identify an Article 6 basis
and an Article 9 condition before processing special-category data, with any required
additional safeguards. Screen for DPIA requirements and complete one before likely
high-risk processing. Supply real privacy, operating-hours, response-expectation
and urgent-help procedures; the service must not imply unstaffed emergency cover.
Provide an operational route for access, correction and erasure requests, and a
security/privacy incident process owned by named people.

Primary guidance reviewed 3 November 2026:

- [ICO: Special category data](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/a-guide-to-lawful-basis/special-category-data)
- [ICO: DPIAs](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/guide-to-accountability-and-governance/data-protection-impact-assessments/)
- [ICO: Right to erasure, including backups and exceptions](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/individual-rights/right-to-erasure/)

These sources inform the design; they do not decide the university's lawful basis,
retention policy or demonstrate institutional legal approval.

## Delivery order and acceptance

1. Confirm account/profile fields, verification/enrolment policy and closure/erasure
   semantics; update threat model, role rules and data contracts with the existing
   architecture as baseline.
2. Implement reusable identity/profile lifecycle and controlled staff onboarding,
   with synthetic automated tests in a separate environment while production stays
   gated until its genuine provider/policies are configured.
3. Add verified real-contact notifications and delivery monitoring. Keep case text,
   diagnoses and internal notes out of emails and logs.
4. Provision the chosen production app/identity/database/worker infrastructure with
   HTTPS, private database access, secrets, monitoring and encrypted offsite backups.
   Domain, provider accounts/budget, named operators and credentials are needed for
   this deployment; none are inferred or created by this plan.
5. Add reviewed service/privacy wording and configure the actual retention/erasure
   policy. Remove fictional branding/demo-only restrictions from the production
   presentation once corresponding controls are genuinely ready. Keep synthetic
   fixtures out of production; do not convert the local test DB into production.
6. Verify signup/verification/duplicate and disabled accounts, recovery, invited staff,
   student isolation, replies, contact changes, reauthentication, closure, erasure,
   lawful retention, concurrent writes, notification failure and restoration after
   deletion. Test retry/crash safety and ensure deleted accounts do not silently
   return on login or restore. Complete human accessibility and independent security
   review, then a small authorised real-user pilot before broader launch.

The next concrete coding increment is account/profile lifecycle plus the approved
single-university enrolment interface. Public deployment, real email and collection
of personal records require the configured infrastructure and privacy/service gates;
they are not accomplished by changing labels or removing validation.
