# Sportabase web product design QA

Status: **PASS — no actionable P0, P1, or P2 findings remain in the locally testable states.**

Audit date: 2026-09-08
Mode: combined product-flow and accessibility audit
Authority: `README.md` → `DESIGN.md` → locked Sportabase semantics → recovered Design Lab

## Audit scope

The audit covers the production Expo web shell and the routes `/`, `/explore`, `/intelligence`, `/settings`, `/watchlists`, `/alerts`, `/notifications`, and `/activity` at 1440, 768, 390, and 320 CSS pixels. It uses screenshots captured from the current local `mobile/dist` export during this implementation run. The recovered Design Lab is treated as a visual reference, not as production data or production component ownership.

Primary user goal: move from analysis or discovery into inspectable intelligence, watches, alerts, activity, settings, or account entry without encountering a different product language or misleading evidence semantics.

Accessibility target: keyboard-operable, responsive product flows with visible focus, honest state communication, useful semantics, reduced-motion support, and resilient reflow. This is not a claim of full WCAG conformance.

## Current-run visual evidence

- Recovered reference: [`design-lab-reference.png`](tooling/browser/artifacts/expo/confirmation/design-lab-reference.png)
- Production home: [`home-desktop.png`](tooling/browser/artifacts/expo/confirmation/home-desktop.png), [`home-mobile.png`](tooling/browser/artifacts/expo/confirmation/home-mobile.png)
- Discover: [`discover.png`](tooling/browser/artifacts/expo/confirmation/discover.png)
- Settings: [`settings-desktop.png`](tooling/browser/artifacts/expo/confirmation/settings-desktop.png), [`settings-narrow.png`](tooling/browser/artifacts/expo/confirmation/settings-narrow.png)
- Protected account interruption: [`watches-account-gate.png`](tooling/browser/artifacts/expo/confirmation/watches-account-gate.png), [`alerts-account-gate.png`](tooling/browser/artifacts/expo/confirmation/alerts-account-gate.png)
- Intelligence detail: [`intelligence-result.png`](tooling/browser/artifacts/expo/confirmation/intelligence-result.png)

The recovered reference is a committed historical artifact. Release Expo exports do not expose a Design Lab route, and browser QA does not regenerate this reference through the release application.

The comparison between the recovered reference and production home shows the identity was carried forward through the same dark evidence-first canvas, selected logo/wordmark, condensed display typography, restrained cyan/lime accents, wide composition, and stationary background-scale SB mark. Fixture storylines and the visible Design Lab affordance were intentionally not copied into production.

## Strengths

- **Flow clarity:** the same production-owned shell makes Analyze, Discover, Watches, Alerts, Activity, Settings, and Account consistently reachable. Evidence: all confirmation screenshots.
- **Hierarchy:** compact uppercase section labels, high-contrast condensed headings, restrained rules, and one dominant action per area retain the recovered sports-intelligence character. Evidence: [`home-desktop.png`](tooling/browser/artifacts/expo/confirmation/home-desktop.png) and [`intelligence-result.png`](tooling/browser/artifacts/expo/confirmation/intelligence-result.png).
- **Trust:** protected entry states describe both the required action and honest local unavailability; they do not substitute Settings or render fake authentication. Evidence: [`watches-account-gate.png`](tooling/browser/artifacts/expo/confirmation/watches-account-gate.png).
- **Semantic restraint:** Discover distinguishes canonical watchable objects from provenance-only sources/reporters, and Intelligence states chronology and evidence-count limits directly. Evidence: [`discover.png`](tooling/browser/artifacts/expo/confirmation/discover.png) and [`intelligence-result.png`](tooling/browser/artifacts/expo/confirmation/intelligence-result.png).
- **Settings architecture:** desktop uses section navigation plus one readable workspace; narrow screens use two-stage section navigation. It avoids promotional layout and decorative controls. Evidence: both Settings confirmation screenshots.
- **Identity consistency:** typography, spacing, surfaces, lime/cyan accents, logo treatment, copy tone, and control geometry now read as one product rather than a themed legacy dashboard. Evidence: the full confirmation set.

## Findings and correction record

| Priority | Lens | Current-run evidence | Finding | Correction | Final state |
| --- | --- | --- | --- | --- | --- |
| P1 | Consistency / perceivability | Initial iteration capture; verified by [`home-mobile.png`](tooling/browser/artifacts/expo/confirmation/home-mobile.png) and [`discover.png`](tooling/browser/artifacts/expo/confirmation/discover.png) | Server and client color-scheme selection could produce mixed light and dark surfaces after hydration. | Added a hydration-safe product color-scheme boundary and synchronized document color scheme/theme color. | Resolved in confirmation set. |
| P1 | Responsive flow | Initial iteration capture; verified by [`settings-desktop.png`](tooling/browser/artifacts/expo/confirmation/settings-desktop.png) and [`settings-narrow.png`](tooling/browser/artifacts/expo/confirmation/settings-narrow.png) | Route/section changes could retain a previous scroll position and hide the page or section entry context. | Remounted page scrolling by route/responsive bucket and explicitly returned Settings content to its top on section transitions. | Resolved in both Settings confirmation screenshots. |
| P2 | Logo quality / responsive composition | Initial iteration capture; verified by [`home-mobile.png`](tooling/browser/artifacts/expo/confirmation/home-mobile.png) | The compact wordmark could wrap or clip, weakening the selected Sportabase mark. | Gave the production wordmark an explicit compact measure and tuned compact typography/logo spacing without replacing the source asset. | Resolved in confirmation set. |
| P2 | Navigation / reflow | [`settings-narrow.png`](tooling/browser/artifacts/expo/confirmation/settings-narrow.png) | At the narrowest width, moving the horizontal nav to its final item could leave a label visibly cut at the opposite edge. | At 320 pixels, primary navigation uses complete compact labels with 44-pixel minimum targets and may wrap if translated copy requires it; wider compact layouts retain the touch- and keyboard-scrollable row. | Resolved in final browser verification. |

## Product Design audit

- **Task entry and discoverability:** Analyze is the public entry task; Discover is clearly differentiated as persisted intelligence search. Protected routes preserve destination intent and provide supported sign-in/create-account actions.
- **Information architecture:** primary navigation remains deliberately limited; Notifications stays reachable from Settings rather than competing as an eighth primary item. Settings taxonomy matches the constitution.
- **Interaction flow and interruptions:** account gating is contextual and reversible. Missing Clerk configuration becomes an inline alert rather than a dead redirect or fabricated form.
- **Hierarchy and consistency:** production home, search, result, settings, and protected states share the same shell, type roles, spacing rhythm, surfaces, and status grammar.
- **Copy/content:** visible copy explains what the system can and cannot infer. No mock storyline, provenance, related-reporting, or verification claims appear as live production content.
- **Colors and assets:** the recovered dark palette and cyan → teal → green → lime identity are controlled rather than decorative. The real SB asset and selected wordmark remain crisp across captured widths.

## gpt-taste critique

The interface is recognizably Sportabase rather than a generic SaaS/fintech template: the large background SB, narrow editorial display face, evidence-boundary copy, sparse rules, and low-card density establish a repeatable signature. The strongest improvement over the initial state is consistency—operational screens no longer fall back to unrelated utilitarian cards. Density is highest in Settings, but the two-column workspace and narrow two-stage flow keep it purposeful. Suggestions for marketing-page AIDA structure, arbitrary gradient additions, or ornamental motion were rejected because they conflict with the recovered product and `DESIGN.md`.

## Impeccable critique

The extraction improved hierarchy, responsive composition, typography roles, surface discipline, target consistency, loading/empty/error grammar, and interaction polish without installing the absent Impeccable engine. The hardening pass specifically addressed hydration consistency, responsive remounting, compact brand composition, focus restoration, dialog keyboard behavior, reduced motion, and long-content wrapping. No additional high-impact polish issue remains in the captured states.

## Web interface guidelines audit

- Landmarks, headings, skip navigation, native/role-based controls, `aria-current`, alerts, and named dialogs are present.
- Keyboard focus is visible and tightly scoped; no global outline suppression was introduced.
- Interactive targets are at least 44 CSS pixels in the tested product controls.
- Hover styling is limited to hover-capable pointers. Reduced motion removes transitions and watermark movement while retaining the static mark.
- Inputs have persistent labels and appropriate autocomplete behavior; errors are rendered near the affected task with retry where meaningful.
- Long titles wrap, the document has no horizontal overflow at tested widths, and the focused 200% zoom check reflows without clipped product content.
- Destructive Settings confirmation uses an explicit close control, Escape, a focus loop, and focus restoration; static component tests cover this because safe signed-in browser access was unavailable.

## Evidence limits and verification gaps

- Real Clerk redirect/authenticated route UI was not exercised: no explicit staging deployment/API/web origin plus Clerk `pk_test_` configuration was supplied. Protected signed-out states were browser-tested without invoking Clerk.
- Authenticated Watches/Alerts data states and the Settings destructive dialog could not be entered in a browser without inventing a session. Their source behavior is preserved and their shared state/dialog components are covered statically.
- Article/video network calls were not sent. The real adapters are covered with mocked unit requests; a public mocked Intelligence result supplies rendered evidence for the result hierarchy and locked chronology/evidence semantics.

These are staging-coverage limits, not unresolved P0/P1/P2 design findings. They remain explicit prerequisites for a later safe authenticated staging run.

## Final recommendation

Accept the local productization baseline. The next gate is an explicitly configured staging build followed by authenticated flow verification; no production deployment or production-data test should occur from this state.

final result: passed
