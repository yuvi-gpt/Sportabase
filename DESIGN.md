# Sportabase design constitution

Sportabase is an evidence-first sports intelligence workspace. People arrive from a live match, a headline or a video and need to understand reporting without mistaking repetition for proof. Account and Settings surfaces are tools: fast to scan, predictable to operate, quiet enough for sustained reading. Preserve the established green identity; never offer an accent picker.

## Visual system

| Semantic role | Light | Dark |
| --- | --- | --- |
| Canvas | #f5f7f4 | #050706 |
| Surface | #ffffff | #0d110f |
| Raised/selected surface | #e8eee7 | #18221b |
| Primary text | #172219 | #f3f7f3 |
| Secondary text | #4e6053 | #a5b3a9 |
| Control border | #718476 | #718477 |
| Divider | #ced8cd | #344539 |
| Brand/action | #246b16 | #78f54a |
| On brand | #ffffff | #071006 |
| Focus | #245dd8 | #a3beff |
| Destructive/error | #a82424 | #ff9a9a |
| Warning | #805600 | #f7ca62 |

High contrast uses near-black/white text, opaque surfaces and 2px control boundaries. Preserve forced-colors support; never disable system color adjustment globally. Semantic states always have words or shapes as well as color. Light mode is a deliberately shaded paper workspace, not inverted dark CSS.

Typography: Geist when bundled, then native/system sans. Native apps use their platform face. Body 16px/1.5; secondary 14px/1.45; row label 16px/600; section title 18px/600; Settings title 28px/600 (24px on narrow screens). No all-capital navigation, tiny captions or oversized headings. Data numerals are tabular. Headlines wrap naturally, with balanced lines and tracking no tighter than -0.03em. Settings has no marketing hero.

Spacing is 4, 8, 12, 16, 24, 32, 48px. Group related rows tightly; use 32px between sections. Comfortable rows have 16px block padding; compact rows 8px, retaining target sizes. Radii: controls 6px, sheets 12px, exceptional content cards 12px. Most settings are divided rows, not individual cards. Canvas < surface < raised gives three meaningful surface levels. One shadow for a floating sheet; no glowing borders, decorative glass or background gradients in Settings.

## Interaction grammar

- Buttons use action verbs, 44px minimum height on touch screens (48dp preferred on Android), 40px on pointer-only surfaces. Destructive actions use a named confirmation and a separate destructive button. Pending writes announce progress, prevent duplicate submits and retain entered values on error.
- Inputs have persistent visible labels, 16px text, appropriate keyboard/input modes, autocomplete, and associated error text. Selects use native semantics. Switches are boolean, have an accessible name/state and only appear for working behavior. Time inputs use explicit timezones.
- Focus is a 3px visible ring with 3px offset. Every action works from a keyboard. Never remove outlines without a replacement. Links remain recognizable and wrap long URLs.
- Web Settings uses a native modal dialog with a named header, close button, Escape, contained focus and focus restoration. Desktop uses a right workspace up to 760px wide. At <=600px it becomes a full-height, two-stage sheet: users choose from a section index, then return with a clear Back to Settings action. No nested scrolling traps or horizontal clipping.
- Mobile uses grouped settings rows with drill-in navigation, safe areas, native switches, wrapping labels and a persistent Analyze / Discover / Watches / Alerts / Settings navigation. Notifications is a Settings destination. Never use a web drawer as native UI.
- Extension extends its existing drawer. Keep panel position, size, remembered layout and reset local to Chrome. Fit within viewport minus 8px gutters; collapse row controls beneath labels in constrained widths. Authentication runs in privileged extension contexts, never the host page.
- Account state is explicit: loading, signed out, signed in, sync error. Landing and intentionally public canonical pages remain readable. Product actions lead to the supported sign-in flow. Never imitate a provider password form.
- Settings taxonomy: Account; Appearance (including contrast, size, density, motion); Notifications; Analysis; My Activity; Language & Region; Privacy & Data; Devices/Sessions; Support/About. Use progressive disclosure, not a wall of toggles. Explain account defaults versus this device at the scope selector.
- Activity rows show safe title, type, timestamp and originating platform, with a clear revisit link. Search, type filters and pagination do not imply canonical relationships. Empty states explain the next useful action. Errors include retry; loading uses text/status or a stable skeleton without layout jumps.

## Adaptation and accessibility

At 320px, stack controls and use the two-stage section index; at 600px switch sheet composition; at 900px give content and navigation separate columns. Respect browser zoom through 200%, system text scaling and long translations. Never cap native font scaling globally. Text size small/default/large changes presentation only; `system` preserves system defaults. No fixed-height text containers. Density never reduces touch hit areas or hides evidence caveats.

Motion follows system/reduce/full. Reduce disables decorative transforms, animated scrolling and chart motion. Full permits a short sheet transition, not constant animation. Prefer state transitions under 180ms. No GSAP, pinning, scrubbing or AIDA structure in operational Settings: the user's task-focused brief overrides those gpt-taste marketing prescriptions. Its useful disciplines here are typography, restrained component counts, readable buttons and overflow checks.

Meet WCAG AA text contrast (4.5:1 normal, 3:1 large) and control distinction (3:1). Use landmarks, real headings, labels, status announcements and native controls. Do not use icons for every row. Do not present decorative switches, digest options without delivery, unsupported languages or broken help links.

## Evidence semantics: immutable

Merit Score describes reporting/informational quality and evidential support, never truth probability. Video Evidence Score, Logic Score and Verdict remain distinct; no composite credibility score. Chronology means ordering, not credibility or novelty. Evidence count is not probability. Repetition and dependency are not independent corroboration. Verified independence requires positive provenance; missing independence does not establish dependence. Sources/reporters remain inspectable provenance objects without a reliability score. Only entity/story/claim/media are watchable. Search is not canonical linkage. Essential detail may collapse supplemental explanation but must retain score definitions, qualifications and distinct dimensions. Preferences never change scores, graph relationships, evidence judgments or reconciliation.

## Reference disciplines

Reviewed the public [awesome-design-md collection](https://github.com/VoltAgent/awesome-design-md): [Vercel](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/vercel/DESIGN.md) for aligned controls and typography; [Supabase](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/supabase/DESIGN.md) for restrained green and surface hierarchy; [Expo](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/expo/DESIGN.md) for readable technical UI; [Apple](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/apple/DESIGN.md) for native hierarchy; [PostHog](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/posthog/DESIGN.md) for navigation and information density. These are inspiration, not authoritative brand specifications or copied identities. Apply Impeccable Operate guidance and [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines) in the final accessibility and design passes.
