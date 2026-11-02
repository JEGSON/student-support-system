# Student registration and own profiles

Explicitly authorised by the user after the Stage 19 handover. This is a local
synthetic extension of ADR-04; it does not introduce Flask password storage or
production self-enrolment. The existing OIDC/PKCE boundary remains authoritative.

## Registration

GET /register explains the demo; GET /register/start initiates ordinary OIDC with
prompt=create, random state/nonce and S256 PKCE. Neither GET creates a principal.
The provider handles the credential/registration POST and its CSRF validation.
An initial Flask POST→provider redirect was blocked by the existing form-action
CSP during browser testing; using a normal GET navigation fixes the handoff
without weakening CSP or allowing external form targets.

After validated issuer/audience/signature/nonce/expiry, an unknown subject may be
mapped to a new student ONLY when SELF_REGISTRATION_ENABLED=1 and the issuer is
exactly http://127.0.0.1:8180/realms/student-support. Config rejects this flag for
production/other providers. Default is 0; the trusted local provisioning command
enables it explicitly. The app never receives/stores a registration password and
never receives provider administrator credentials. Existing disabled principals
remain denied; matching never uses email, username or supplied student reference.

Issuer+subject uniqueness makes repeat/concurrent callbacks return one principal.
Creation and attributed account_created audit commit atomically. New roles are
always [student]; supplied provider roles/groups/reference/contact are ignored.
The student reference and reserved local notification address are server-generated;
no real email delivery is possible. Failed audit rolls back account creation.
Privileged roles still require the existing independent controlled grant process.

The local Keycloak realm enforces @example.invalid email addresses, 12-character
passwords with upper/lower/digit, uniqueness and brute-force protection. Synthetic
contacts do not establish real contact provenance or university eligibility.
The password composition policy is a local demo choice, not institutional policy.
Production registration would require eligibility, identity/contact verification,
abuse controls, approved policy and a separately reviewed rollout.

## Profile

GET /account/profile returns only the current user's preferred name, optional
course, reference/local notification address and profile_version. A required safe
profile_read audit precedes display. POST uses signed CSRF and exact field/shape
allowlists: csrf_token, version, display_name, course_label. Names are required;
course may be cleared. Both fields allow up to 160 plain-text characters, reject
control characters and render escaped. No arbitrary target identifier is accepted.

Role/team/status, identity, student reference and notification destination are not
self-editable. Active status is checked inside the transaction. profile_version
and shared account guard writes reject stale tabs/concurrent revocation. Updates
and metadata-only profile_updated audits commit together; no name/course values
enter audits. Optional profile_version/profile_updated_at extend the users schema
without requiring a destructive migration. Existing profiles start at version 0.
Other students/case ownership are unchanged; there are still 18 collections.

Evidence: [account/profile checks](../evidence/account-profiles/README.md).
Primary provider guidance: [Keycloak registration and profile validation](https://www.keycloak.org/docs/26.2.5/server_admin/).
No real student information or external account/service was used.
