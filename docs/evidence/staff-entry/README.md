# Staff entry discoverability — 3 November 2026

The user could create a student account/request but could not find how university
staff receive or reply to it. Existing provisioned manager/officer/admin accounts
were confirmed active using metadata only; no password was printed or published.
A public /staff/sign-in guide is now linked from the homepage and student account.
It explains individual approved staff accounts, access administration, team scope,
assignment/start/reply and the student's Conversation view. No role changes,
public staff signup or additional case visibility were introduced.

139 unit/authorisation/staff-work/communication/browser checks passed, zero failures,
errors or skips. Complete real Chromium/WebKit case journeys at 390/768/1440 now
enter staff login through the homepage guide, then assign/start/question/reply/note/
refer/close and check student isolation and expiry/conflicts. Six additional public
guide renders passed overflow and selected axe WCAG checks; phone/desktop screenshots
were visually inspected. This is scoped evidence, not full accessibility conformity.
The previous whole-project 301-pass result remains the earlier integrated checkpoint.

The verified existing project runner on 5050 was restarted; homepage and staff-entry
HTTP checks returned 200. Database/accounts/request records were preserved. Local
credentials remain in ignored runtime/synthetic-logins.json. For a finance demo use
manager_finance; managers can allocate an eligible officer and reply within their
team scope. New staff identity provisioning and institutional policy remain separate
from public student self-registration. No remote push or production deployment was
performed as part of this discoverability change.
