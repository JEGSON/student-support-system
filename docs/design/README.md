# Visual design and user experience specification — Stage 02

Direction: calm, precise and welcoming. Warm off-white canvas, deep navy text,
restrained teal actions, substantial whitespace and quiet borders. No stock imagery,
remote fonts, tracking, fabricated metrics, testimonials or monitoring promises.
System fonts and original CSS only; no external asset requests. Brand mark is an
original typographic placeholder, not a university crest or approved identity.

Start with the [service entry prototype](prototypes/index.html). Eight isolated
static pages demonstrate layout and states. The dark design-review bar links them;
that bar is not product navigation. All records are synthetic. Prototype actions
navigate between examples; no authentication, submissions, storage or permissions
are implemented. Keep these artefacts out of production routes. Do not enter real
personal information in a preview.

## Information architecture and working contexts

Public: service entry → OIDC sign-in → explicit student/staff context if applicable.
Student: My support → New request → own case → student-visible conversation/outcome.
Staff: scoped metadata queue → authorised case workspace → messages/notes/actions.
Triage: metadata queue → explicit expiring claim → initial request/routing only.
Administration: accounts → membership proposal → independent approver decision.
Audit reviewer: approved metadata scope and purpose; no routine narratives.

Render only the navigation and actions authorised for the selected context.
Student ownership never unlocks notes. Administrators receive administrative
metadata, not case content. Do not send inaccessible controls or content to the
browser and hide it using CSS. These are requirements for later server policies,
not claims that this static design authenticates viewers.

## Tokens and geometry

`prototypes/design.css` is the canonical Stage 02 token source. Stage 03 will copy
its shared rules into the application design system rather than adding arbitrary
screen-specific palettes. Use semantic custom properties.

| Token | Value | Use |
| --- | --- | --- |
| canvas / surface | `#f7f6f2` / `#ffffff` | Quiet page / content panels |
| ink / muted | `#172e3b` / `#53656b` | Headings/body / supporting text |
| teal / teal-hover | `#12675f` / `#0c5049` | Primary action and links |
| tint | `#e9f3ef` | Supportive panels and staff messages |
| navy | `#122c39` | Brand context and design-review bar |
| line / input-border | `#d7dfdc` / `#788b88` | Decorative rules / essential field edges |
| amber / amber-bg | `#704e16` / `#faf0d9` | Needs attention and staff-only note panel |
| red / red-bg | `#9d3435` / `#fff0ee` | Errors and destructive confirmations |
| focus | `#145dba` | 3px outline, 4px offset; no outline removal |

Calculated sRGB contrast ratios: ink/canvas 13.03:1; muted/surface 6.10:1;
muted/canvas 5.64:1; white/teal 6.71:1; teal/tint 5.92:1; amber/amber-bg
6.64:1; red/red-bg 6.37:1; input-border/white 3.59:1; focus/canvas 5.88:1;
focus/tint 5.61:1. These calculations validate token pairings, not full WCAG
conformance. Do not use decorative `line` as the only field boundary.

Spacing scale: 4, 8, 12, 16, 24, 32, 48 and 64px. Body 16px/1.55, hint 13.6px,
section heading approximately 21px, page heading fluid 32–46px, entry hero 42–66px.
System sans stack. Body copy target 45–70 characters per line; leads max 58ch.
Limit long narrative blocks to 70ch in runtime templates. Do not truncate required
case descriptions; wrap long words safely. Use UTC machine values with
Europe/London labels; examples use explicit dates rather than fabricated recency.

Maximum content width 1200px; 32px desktop and 16px phone side gutters. Main
workspace uses remaining width + 300px context column with 32px gap. At 1000px
reduce to 260px and 24px; at 760px stack in DOM reading order. Equal-width cards
use a two-column grid above the same breakpoint. Panels use 12px corners,
controls 6px; 1px quiet rules; no drop shadow by default. Essential controls have
at least 46px height. Product navigation targets at least 44px. Icons are simple
inline glyphs/locally authored SVG with visible labels; decorative icons use
`aria-hidden`. Do not rely on colour or icons alone to convey state.

## Screen layouts and annotations

Each prototype includes a visible design annotation. The order below also serves
as a structural wireframe: header/navigation → title/action → primary work → context.

| Screen and prototype | Hierarchy, action and permission boundary | Mobile adaptation |
| --- | --- | --- |
| [Service entry](prototypes/index.html) | Public brand; left explanatory hero and one OIDC action; right three-step explanation; support areas; pending service wording. No case data. | Hero/action first, explanation below; topics wrap. |
| [Student overview](prototypes/overview.html) | Title/new request action; own-case cards with reference/status and question needing attention; secondary information panel. No notes or staff actions. | Action below title, case cards and context stack; dates wrap. |
| [Request form](prototypes/request.html) | Required category and narrative with hints; privacy/service placeholder; submit/cancel; optional explanatory aside. Server owns identity/status/routing. | One-column labels/fields; no horizontal form layout. |
| [Student case](prototypes/case.html) | Reference/status; student-safe conversation/timeline and labelled reply; case facts; what happens next. No note markup or note events. | Conversation first, context below; authors/times wrap independently. |
| [Staff queue](prototypes/queue.html) | Restricted metadata only: reference, category, submitted time, status, team. Labelled filters and bounded pagination; no names or narratives. | Rows become labelled cards preserving all five fields. No arbitrary column hiding or accidental overflow. |
| [Staff workspace](prototypes/workspace.html) | Assigned-officer/scoped-manager context; student-visible messages first; amber staff-only note panel visibly separate; assignment facts. Manager-only actions rendered separately when authorised. | Conversation, notes, then context. Inline action confirmation, no modal-dependent workflow. |
| [Access administration](prototypes/access.html) | Account/membership metadata; requester and independent-approval state; no narratives. Grant decision belongs to a separate approver projection. | Full-width grant panel followed by boundary explanation. |

Queue reference links are design navigation. The runtime must enforce the same
scope on individual views and counts: unassigned officers and administrators cannot
read narratives; triage claim is audited, at most 30 minutes, initial request only.

## Reusable components and states

| Component | Contract and required states |
| --- | --- |
| App shell/navigation | Semantic header/nav/main/footer, skip link; explicit selected working context. Mobile navigation wraps visibly; no hover-only menu. |
| Page header | Eyebrow, one h1, brief description and primary action; mobile action below heading. |
| Button/link | Descriptive action, primary/secondary/destructive variants, visible keyboard focus, processing label and busy state. Disable duplicate click while retaining server idempotency. |
| Field | Visible label, required wording, associated hint/error, maxlength where relevant, server validation. Do not use placeholder as label. |
| Error summary | Focus on invalid POST response, links to invalid fields, field values escaped and retained only in response. No sensitive drafts in localStorage. |
| Alert | Success `role=status`; dynamic blocking error `role=alert`; ordinary information non-interrupting. Plain text and generic safe failure, no topology. |
| Status badge | Text New / In Progress / Awaiting Student / Closed. Archive is a separate flag. Meaning never conveyed by colour alone. |
| Case card | Authorised reference/status/title/context/date and actionable question. Empty overview offers a new request. |
| Queue and pagination | Scoped metadata and filters; labelled mobile card fields; stable bounded pagination; proper table/list semantics in implementation. |
| Conversation | Explicit safe projection with author/time/body; long text wraps; timeline excludes note events. Plain text only. |
| Internal-note panel | Separate staff retrieval/template; amber label “Staff only”; append correction history; never student HTML or notifications. |
| Confirmation | Inline destination/action, reason or outcome required, confirm/cancel. Closure only from In Progress; independent privilege approval; no arbitrary status dropdown. |

[State gallery](prototypes/states.html) includes empty, processing, success,
validation error, expired session, generic not-found/unauthorised case, conflict,
closed/archived and save/audit failure patterns. Production administrative forbidden
response is generic 403; unauthorised case response is consistent 404. Public
sign-in redirects must use a validated local return path. An OIDC failure uses a
safe retry message. Closed student view omits composer and shows the resolution;
reopening follows the manager process and institution-approved contact guidance.
Preserve safe usability around timeout without retaining narratives in browser
storage; exact in-memory/response behaviour needs session threat review in Stage 05.

## Accessibility and interaction

Aim for WCAG 2.2 AA core journeys, without claiming conformance before verification.
Use semantic headings/landmarks, explicit form labels, DOM order matching visual
order, keyboard operation, visible focus and status text. Review 200% zoom and
screen-reader error announcements when runtime tooling is available. Prefer a
44–46px target policy; WCAG 2.5.8 has a 24px minimum with specified exceptions.
Focus outline is deliberately stronger than colour-only focus; the additional
WCAG 2.4.13 appearance criterion is AAA, not an AA certification claim. Honour
`prefers-reduced-motion`; no essential motion, animation or auto-scrolling is used.

Primary guidance checked for this specification:
[WCAG 2.2](https://www.w3.org/TR/WCAG22/),
[focus appearance](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance).

## Decisions, preferences and limitations

Proceed with this proposed direction; institution branding, service wording,
privacy notices, hours, access approval and urgent-help text remain OD-03/04/05/07.
No university approval inferred. No design change expands features or permissions.
ADR-02 remains Flask/Jinja; no frontend framework substitution.

The preview server returned HTTP 200. Browser automation inventory reported its
host unavailable; native Chrome connections timed out twice. No rendered screenshot,
keyboard, zoom, phone/tablet/desktop or screen-reader inspection is claimed in
Stage 02. Static responsive rules and contrast calculations were checked. The
prototypes remain directly reviewable in a local browser. Stage 03 must record
rendered verification or remain incomplete under its stricter completion gate.
