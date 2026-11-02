# Stage 02 — design evidence

Date: 2 November 2026, Europe/London. Source foundation commit: `dc42107`.
Design changes are in the enclosing Stage 02 commit. Operator/reviewer: Codex,
self-review only. Fixtures: inline synthetic design examples v1, no accounts.

## Changes and actual checks

- Added `docs/design/README.md`, shared prototype CSS, seven annotated screen
  layouts plus a state gallery, and `scripts/check_design.py`.
- `python3 scripts/check_design.py`: PASS, eight synthetic static pages, one h1 per
  page, all fields labelled, no remote requests/scripts/form submissions; student
  pages omit the staff-note fixture and note composer. Eight planned contrast
  pairings meet specified 4.5:1 text / 3:1 control thresholds. This is a static
  artefact check, not an application policy test or full accessibility audit.
- `python3 scripts/check_foundation.py`: PASS; planning coverage unchanged;
  197 document links valid before evidence/update links were added. Final output
  can have additional valid documentation links.
- Static server: `python3 -m http.server 8765 --bind 127.0.0.1 --directory
  docs/design/prototypes`. Sandbox blocked bind, so retried with approved escalation.
  `curl --fail --silent -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/`
  also required approved escalation and returned 200.
- Computer-use inventory: browser host unavailable. Two native Chrome connection
  attempts timed out (approximately 38 and 60 seconds). No screenshot was captured;
  no rendered width, keyboard, reduced-motion emulation or screen-reader result is
  claimed. Responsive CSS specifies 760px/1000px breakpoints for later inspection.

Stage 02 permits explicit visual-inspection limitations; reviewable prototypes and
specification exist. Stage 03 has a stronger rendered/runtime verification gate and
must not be marked complete without resolving or explicitly reporting missing work.
All V01–V16 application verifications remain unrun. T05/T06 boundaries are reflected
in separate design documents; no security boundary or policy changed. Institutional
wording, branding and actual access approvals remain open, with synthetic placeholders.
