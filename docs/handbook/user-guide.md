# Student, staff and access-administration guide

Use generated private credentials; labels below have no default password. Sign in
with the university-account button, then choose the explicit context if multiple
are available. Logout is a CSRF-protected local action through Your account. It
does not terminate Keycloak/university SSO; shared-device users must also follow
the provider's logout process.

## Students

student_a and student_b have separate ownership. Open Your requests → New support
request. Choose a support area, describe a synthetic concern (up to 10,000 plain-text
characters), then send. The server chooses owner/team/New status and returns a
reference. Open the case to read messages and reply. A reply to Awaiting Student
returns it to In Progress. New/In Progress messages do not change status. Closed
cases are read-only; follow the university's published process to request reopening.
Corrections append an entry and retain the original; no silent editing/deletion.

Retry the same form after an unconfirmed submission; changing its text after a
successful submission conflicts. A new request needs a new form/key. Drafts are
not saved to localStorage. If a session/form expires, sign in again and open a new
form; the expired POST makes no business change. Never put real diagnoses, bank
information, passwords or another person's details into this demo.

## Staff and managers

Staff context → Staff workspace. Queues show reference, category, submitted time,
status and responsible team, not narrative previews. Officers see assigned cases;
managers see current team scope. Triage members may claim an initial New request
for at most 30 minutes. That audited view exposes initial request/necessary identity
only. It grants no later messages or internal notes. Routing requires a matching
active team; release the claim when finished. Expiry/revocation is checked again.

manager_finance allocates finance work. Assignment requires an eligible active
team member and a reason; it leaves New unchanged. officer_assigned can then use
Start assigned work, explicitly New → In Progress. A question changes In Progress
→ Awaiting Student atomically. Record internal notes only in the amber staff-only
area; neither note bodies nor note events enter the student timeline or emails.
Close only In Progress and supply a student-visible outcome. Resume Awaiting Student
with a reason before closure. A scoped manager can reopen Closed with a reason and
an eligible assignee. Stale versions produce a review/retry conflict, not overwrite.

Other accounts: officer_unassigned (same-team denial until assigned), officer_other
(disability), manager_disability, manager_academic, manager_accommodation,
manager_wellbeing, officer_accommodation, officer_wellbeing and triage (finance).
A disabled account cannot authenticate even if its IdP password is valid.

## Controlled referrals

The assigned officer proposes purpose and a deliberate minimal summary. Choose a
different target team and a category that team covers. Source manager reviews and
approves. Only then does the target manager see selected summary/purpose and necessary
identity. Target acceptance creates a separate New target case with no assignee;
source status/content is unchanged. Source descriptions, messages and notes are not
inherited. Target rejection and source withdrawal are explicit terminal decisions;
withdrawn unapproved proposals remain invisible to the target. Repeated/concurrent
acceptance returns the single created case. Institutional sharing grounds are pending.

Required examples: officer_accommodation → manager_accommodation approves →
manager_wellbeing accepts; and officer_other on disability → manager_disability
approves → manager_academic accepts. Managers first assign/start newly submitted
cases as appropriate. The two scenarios also have direct service regression tests.

## Access and lifecycle

administrator manages metadata in admin context. Ordinary officer/triage memberships
can be granted/revoked; manager/admin/approver/audit grants require a pending request
and separate approver who is neither requester nor target. approver signs in
separately to decide. Changes revoke target sessions; sign in again for new contexts.
No routine narrative access is granted to administrators or approvers. Dual student/
staff roles never combine contexts. Offline bootstrap is synthetic-only and explicit.

Reassignment review identifies active cases whose assignee is disabled/revoked or
missing. Managers archive only Closed cases. Routine views then exclude them;
a separate scoped manager archive view requires purpose and successful audit.
Admin retention review is metadata only. Apply holds, or request disposal under the
explicit synthetic one-day policy. Real retention is unconfigured. A separate
approver must approve; the offline maintenance executor alone can erase linked
records. The automated lifecycle tests exercise backdated synthetic examples so
users do not need to wait a day. No automatic case TTL or production disposal runs.

Case-scoped audit review uses the explicit AuditReader service and separate offline
read credential; no general audit export/dashboard is exposed in the website.
Approved case/team scope and purpose are required. Forensic review of already
removed/archived records needs a separately approved operator procedure; there is
no unrestricted reviewer bypass. See operations.md and known-limitations.md.
