# Stage 14 observed accessibility/UX review

Eight browser checks passed in 31.24s: complete student/staff question-reply-note-outcome/referral-isolation flows in Chromium and WebKit at 390/768/1440, plus keyboard skip-link and 200% text-reflow checks. 36 page states returned zero axe-core 4.14.0 WCAG A/AA-tag violations. Screenshots and per-state reports are alongside results.xml.

Controls, labels, focus/skip target, long text, notes separation, stale version and expired forms were exercised. WebKit uses Option-Tab for link focus under its default Mac preference. Reflow test is text resizing, not a claim that native browser zoom/screen-reader testing is complete. Native VoiceOver/screen-reader review remains a handover gap. No full WCAG conformance claim. Reviewed primary WCAG 2.2: https://www.w3.org/TR/WCAG22/.

Developer-only checker: npm install --prefix runtime/accessibility axe-core@4.14.0 --ignore-scripts --no-audit --no-fund. No axe script ships to users; normal CSP stays script-src none.
