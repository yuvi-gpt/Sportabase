# SPORTABASE — SPORTY UI OVERHAUL BRIEF

## IMPORTANT

You are redesigning an EXISTING production-oriented Expo / React Native application.

Do not create a replacement project.
Do not migrate to Next.js, Vite, or a web-only stack.
Do not replace Expo Router.
Do not alter backend behavior.
Do not rewrite the analysis algorithms.
Do not change API contracts.

Work inside the existing `mobile/` Expo application.

Read before editing:

- `mobile/package.json`
- `mobile/PRODUCT.md`
- `mobile/DESIGN.md`
- `mobile/ui-audit/DESIGN_DIRECTION.md`
- `mobile/src/app/index.tsx`
- `mobile/src/components/article-analysis-results.tsx`
- `mobile/src/components/video-analysis-results.tsx`
- `mobile/src/lib/api.ts`
- `mobile/src/lib/youtube-transcript.ts`

The previous design direction in `mobile/DESIGN.md` is visually outdated.

Where this brief conflicts with the old editorial/publication aesthetic,
THIS BRIEF TAKES PRECEDENCE.

---

# PRODUCT

Sportabase is sports intelligence.

A user pastes ONE URL.

Sportabase automatically determines whether it is:

- a sports article
- a YouTube video

The user must NEVER choose Article mode or Video mode manually.

Preserve the existing automatic routing.

Article analysis and YouTube transcript/video analysis already work.

Do not change those flows.

---

# WHY THIS REDESIGN EXISTS

The current interface is too:

- editorial
- newspaper-like
- office-like
- academic
- static
- restrained
- serif-heavy

It feels like a financial research report.

That is NOT the desired product identity.

Sportabase should instead feel like a modern high-performance sports product.

Think:

- elite football analytics
- F1 telemetry
- broadcast match graphics
- scouting intelligence
- live performance dashboards
- modern sports media
- sharp data visualization
- premium sports technology

NOT:

- Microsoft Office
- Bloomberg terminal clone
- newspaper
- consulting report
- corporate SaaS
- generic AI dashboard
- crypto dashboard
- gamer RGB interface

---

# VISUAL PERSONALITY

The interface should feel:

FAST
SHARP
ATHLETIC
PRECISE
PREMIUM
TECHNICAL
SPORTS-NATIVE
ENERGETIC

without becoming childish or esports-looking.

The finished product should look like an intentional sports brand,
not something generated from a generic AI UI template.

---

# BRAND COLORS

The existing Sportabase logo is the source of truth.

Preserve the real logo.

Build the accent system around its lime-to-teal range.

Primary accent direction:

LIME
#B5F36B

BRIGHT SPORT GREEN
approximately #82E85B

TEAL
approximately #20C9B0

CYAN-TEAL
approximately #16B8C4

Use a controlled lime -> green -> teal gradient.

Use gradients for:

- primary Analyze action
- active score rails
- key intelligence indicators
- selected/active states
- very thin accent lines
- restrained edge details

DO NOT fill the entire page with glowing gradients.

The background should remain near-black / charcoal.

Suggested foundation:

#070A09
#0B0F0D
#101512
#171D19

The accents should feel luminous because the surrounding UI is restrained,
not because everything has a glow effect.

---

# TYPOGRAPHY

REMOVE the current newspaper/serif identity.

Do not use Georgia for the main visual language.

Use a modern sports/performance typographic system.

Good directions include:

- Barlow
- Barlow Condensed
- Archivo
- Archivo Narrow
- DIN-like sports typography
- another modern condensed athletic sans if appropriate

Headlines should feel compact, strong and fast.

Numbers should be particularly strong.

Merit scores, Evidence scores and Logic scores should feel like performance metrics.

Avoid giant soft marketing headlines.

---

# GEOMETRY

Make the geometry SHARPER.

Prefer:

- 0px to 8px radii
- angular separators
- hard horizontal rails
- clipped-looking composition where Expo-safe
- strong alignment
- asymmetric data groupings
- inset lines
- compact information clusters
- narrow vertical dividers
- performance-style score tracks

Avoid:

- giant rounded rectangles
- floating rounded cards
- endless card grids
- pills everywhere
- glassmorphism
- fuzzy shadows

Panels are allowed when they communicate hierarchy,
but they should feel engineered rather than soft.

---

# HOMEPAGE

Completely reconsider the composition.

Do NOT simply restyle the existing layout.

The current large text / office-report structure is not the target.

Build a modern sports-intelligence landing workspace.

The first viewport should immediately communicate:

SPORTABASE
SPORTS INTELLIGENCE
ONE SOURCE
ANALYZE

Possible composition:

1. Compact high-performance masthead.
2. Strong athletic product statement.
3. One large universal source command bar.
4. Small intelligence signal rail:
   MERIT / EVIDENCE / INDEPENDENCE / CLAIM STATUS
5. Sharp supporting product information.

The universal URL bar should be one of the strongest visual elements.

There must be:

ONE URL FIELD
ONE ANALYZE ACTION

No Article / YouTube tabs.

No mode selector.

No implementation explanation such as:

- "Automatic source detection"
- "Article / YouTube"

The product should simply behave intelligently.

---

# SPORTABASE IDENTITY

Introduce restrained sports visual language.

Examples:

- thin diagonal motion lines
- subtle pitch/grid/telemetry structure
- speed-inspired dividers
- angular score rails
- scoreboard-like numeric typography
- performance-data rhythm

Keep these subtle.

Do NOT turn Sportabase into an esports HUD.

The user should think:

"premium sports intelligence platform"

not:

"gaming overlay."

---

# ARTICLE RESULT

The article result should feel like a modern sports intelligence breakdown.

Keep these concepts separate:

MERIT
EVIDENCE STATUS

Merit is NOT a truth probability.

No corroboration does NOT mean false.

Do not undo those semantics.

Primary hierarchy should include:

- source/article identity
- headline
- Merit score
- Evidence status
- concise summary
- Merit reasoning
- evidence intelligence

Make the Merit score feel like an athletic performance metric.

Use sharper score rails and stronger numerical typography.

Evidence status should be visually distinct from Merit.

Avoid rebuilding everything as cards.

---

# VIDEO RESULT

Preserve the current correct semantic model:

EVIDENCE
LOGIC
VERDICT

Do NOT recreate an "Overall Support" score.

Do NOT average Evidence and Logic.

The previous aggregate was deliberately removed because it was not a backend-defined metric.

Make Evidence and Logic visually equivalent primary performance metrics.

Verdict should be prominent without pretending it is another numerical score.

Preserve:

- content type
- transcript metadata
- evidence used
- logic check
- hype check

---

# RESULT WORKFLOW

Once a report exists:

the report is the hero.

The source-entry control should remain available,
but compact.

Do not let "Analyze another source" dominate the result page.

---

# MOTION

Use motion sparingly but make the app feel responsive.

Preferred:

- opacity
- transform
- short movement
- score-line reveal
- quick state changes

Typical duration:

120ms to 220ms

Respect reduced-motion preferences.

Do not animate:

- width
- height
- padding
- margin

Avoid expensive layout transitions.

---

# RESPONSIVENESS

This is one Expo application for:

- desktop web
- mobile web
- iOS
- Android

Desktop should use the available width confidently.

Mobile should recompose rather than simply shrink.

Verify at minimum:

1440 x 1000
390 x 844

---

# ACCESSIBILITY

Maintain strong contrast.

Body text must remain easily readable.

Do not achieve a "futuristic" appearance by making text tiny or dim.

Interactive controls need obvious states.

---

# TECHNICAL CONSTRAINTS

Preserve:

- Expo SDK
- Expo Router
- React Native architecture
- automatic article routing
- automatic YouTube routing
- YouTube transcript acquisition
- article API calls
- video API calls
- API health indicator
- deep-link/share handling
- hydration fix
- reduced-motion compatibility

Do not touch:

- `backend/`
- `extension/`
- `frontend/`

The static `frontend/` directory contains unrelated local work.

Do not modify it.

Work ONLY inside `mobile/`.

Use Expo-compatible dependencies only.

`expo-linear-gradient` is already installed and may be used.

If adding fonts or UI dependencies, install them using Expo-compatible versions.

---

# QUALITY BAR

Do not stop after changing colors and typography.

This is a structural visual overhaul.

Actively redesign:

- hierarchy
- composition
- density
- rhythm
- score presentation
- information grouping
- navigation feel
- responsive arrangement

Do not merely skin the current layout.

At the same time:

DO NOT change the underlying product behavior.

---

# VALIDATION

Before declaring completion:

1. Run TypeScript validation.
2. Export Expo Web successfully.
3. Inspect the live web preview.
4. Check desktop around 1440px.
5. Check mobile around 390px.
6. Exercise an article result state.
7. Exercise a video result state.
8. Confirm no page errors.
9. Confirm one universal source workflow remains.
10. Confirm Evidence / Logic / Verdict remain separate for video.
11. Confirm Merit and Evidence remain separate for articles.

If something visually feels generic or office-like,
continue iterating before stopping.

---

# DELIVERABLE

Perform the redesign directly in this repository branch.

Do not only give recommendations.

Do not return a mockup instead of implementation.

Do not replace working functionality.

Implement the complete visual overhaul inside `mobile/`.
