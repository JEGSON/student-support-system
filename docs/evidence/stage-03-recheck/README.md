# Stage 03 redo — completed

2 November 2026, Europe/London. Source checkpoint `ccfc591`; changes/evidence are
in the enclosing Stage 03 completion commit. Codex self-review only. Synthetic
inline gallery v1; no student accounts or actual case-management routes.

Reread the detailed architecture baseline, draw.io's eight views, overview,
Stage 02 specification and Stage 03 contract. Retained the Flask/Jinja modular
monolith, service-policy boundary, MongoDB replica-set requirement, OIDC target,
separate notes and transactional outbox. No framework or permission-model change.

## Actual verification

- Locked Playwright 1.64.1 as a development dependency after checking official
  emulation/browser/screenshot documentation. The user explicitly authorised
  isolated Playwright browser tests after native access repeatedly failed.
- Downloaded browsers to ignored `runtime/playwright-browsers`: Chromium
  156.0.8078.4 and WebKit 27.2. This is Playwright WebKit, not a claim of full native
  Safari/device certification. No personal browser profiles or third-party pages.
- Final command: `RUN_BROWSER=1 RUN_RUNTIME=1
  PLAYWRIGHT_BROWSERS_PATH=runtime/playwright-browsers .venv/bin/python -m pytest -q`.
  Result: **29 passed in 77.89s**. Six browser configurations each inspect the actual
  public entry, component gallery, student shell and staff shell; 24 normal and six
  focused-field screenshots saved. Exact viewport widths 390/768/1440, height 1000,
  en-GB locale and Europe/London timezone. JSON records list browser versions.
- Browser assertions: HTTP 200, one h1, no horizontal overflow, working skip-link
  keyboard focus/visible outline, invalid-field focus styling, queue metadata
  preserved, disabled processing example, reduced-motion media emulation with no
  active animations, no external requests and no page errors. WebKit uses Option-Tab
  for link navigation; Chromium uses Tab. No OS-wide keyboard preference changed.
- Reran actual dependency readiness, cross-database credential denial and real
  aborted transaction. Generic errors, missing secrets, prod/test gallery exclusion
  and configuration isolation still pass. Local DB URIs now reject external hosts;
  discovery readiness rejects oversized/non-object documents and non-list methods.
- Exported runtime-only requirements from the frozen lock, created ignored
  `runtime/stage03-clean-env` and installed all ten runtime packages with
  `uv pip sync --require-hashes --offline --cache-dir runtime/uv-cache`.
  Clean-environment smoke test: entry 200, dependencies ready, case route 404,
  missing-secret startup rejection. Initial uv commands hit a default-cache
  permission error; reran with approved escalation and project-local cache.

## Failures and fixes

- Three new malformed-discovery tests initially failed because the factory's
  blueprint variable shadowed the `app.health` module for monkeypatch resolution.
  Aliased the blueprint import; rerun unit suite: 22 passed, seven opt-in skips.
- Initial browser run was interrupted after three failures: exact-text selectors
  ignored mobile label children/uppercase styling, and WebKit required Option-Tab.
  Corrected selectors and browser-specific keyboard input; browser suite passed
  six configurations in 77.28s. Added guaranteed context/browser cleanup on failure.
- Visual inspection identified a compressed tablet header action label. Allowed
  page headers to wrap and prevented action-button shrinking in the canonical
  prototype/application CSS. Final 29-test run captured the refined layout.

## Visual review

Inspected representative saved images for all four screens across phone/tablet/
desktop, including Chromium and WebKit output: heading/body wrapping, spacing,
button labels, card alignment, queue labels, status text and visible field focus.
Phone content stacks; tablet/Desktop grids remain readable. Mobile queue retains
all five approved metadata fields. No observed clipping or accidental horizontal
scroll remained. Default screenshots are separate from focused-field screenshots.
This is scoped runtime-shell review, not full WCAG or future journey conformance.

| Example | Phone | Tablet | Desktop |
| --- | --- | --- | --- |
| Entry | [390](screenshots/chromium-390-entry.png) | [768](screenshots/chromium-768-entry.png) | [1440](screenshots/webkit-1440-entry.png) |
| Components | [390](screenshots/chromium-390-components.png) | [768](screenshots/webkit-768-components.png) | [1440](screenshots/chromium-1440-components.png) |
| Student shell | [390](screenshots/webkit-390-student.png) | [768](screenshots/chromium-768-student.png) | [1440](screenshots/webkit-1440-student.png) |
| Staff shell | [390](screenshots/webkit-390-staff.png) | [768](screenshots/chromium-768-staff.png) | [1440](screenshots/webkit-1440-staff.png) |
| Focus example | [390](screenshots/chromium-390-focus.png) | [768](screenshots/webkit-768-focus.png) | [1440](screenshots/webkit-1440-focus.png) |

Recovered native Safari access solely to resolve the prior temporary preference.
Advanced showed developer features ON; restored to OFF and verified checkbox value
0. Closing settings timed out, but restoration itself was verified. Privacy,
security and keyboard-navigation preferences were unchanged.

Stage 03 is complete. V14/V16 have scoped partial evidence; full accessibility and
production/release verification remain later stages. Next is Stage 04 persistence
contracts/fixtures, then Stage 05 identity. No sign-in, case management, push,
production deployment or real student processing has been performed.
