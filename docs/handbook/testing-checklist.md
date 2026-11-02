# Start here: your local test

Use synthetic text only. Start Docker, then in the project terminal run:

```sh
cd /Users/wealth/Documents/Codex/2026-11-02/go/student-support-system
.venv/bin/python scripts/start_dependencies.py
.venv/bin/python scripts/database_setup.py --environment development --seed
.venv/bin/python scripts/configure_routing.py
.venv/bin/python scripts/provision_identity.py
.venv/bin/python scripts/run_local.py
```

If an older server occupies 5050, stop it with Ctrl-C in its own terminal and run
the last command again. Open http://127.0.0.1:5050. Private generated credentials
are in runtime/synthetic-logins.json. Do not share that file. If starting from a
fresh extract, first follow setup.md; the packaged source deliberately has no secrets.

1. Sign in as student_a. Create a finance request with invented text; note its reference.
2. Sign out; manager_finance → staff workspace → assign to officer_assigned. New stays New.
3. officer_assigned → start work, add an internal note, then ask a student-visible question.
4. student_a → answer. Check In Progress and confirm no internal note is visible.
5. officer_assigned → close with an outcome. student_a sees the outcome and read-only case.
6. manager_finance can reopen with a reason/eligible assignee. Try two tabs and a stale
   version; the second update should ask for review/retry.
7. student_b cannot open the first student's URL. officer_unassigned cannot read an
   unassigned narrative. administrator manages metadata but cannot read case content.
8. For referrals: submit accommodation, manager_accommodation assigns officer_accommodation,
   officer starts/proposes wellbeing with minimal summary, manager_accommodation approves,
   manager_wellbeing accepts. A separate New case appears; source notes do not transfer.
9. Repeat disability → academic using officer_other, manager_disability and manager_academic.
10. In another terminal run `.venv/bin/python scripts/run_worker.py --environment development --once`.
    Inspect http://127.0.0.1:8025: email is generic, with no narrative/category/notes.

For expiry, keyboard, mobile layouts, retention and delivery-failure demonstrations,
see the user guide, handover and automated regression suite. Expired forms fail
without business changes. Capture reference/request ID when reporting issues;
never copy secrets or personal information into an issue.
