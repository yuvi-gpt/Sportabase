# Sportabase product identity design QA

Source visual truth: `tooling/browser/artifacts/expo/confirmation/design-lab-reference.png`

Implementation screenshots:

- `tooling/browser/artifacts/expo/watermark-vercel-stage-repair/home-desktop.png`
- `tooling/browser/artifacts/expo/watermark-vercel-stage-repair/home-mobile.png`

Viewport and normalization:

- Desktop source and implementation: 1440 x 1000 pixels, 1440 x 1000 CSS viewport, device scale factor 1.
- Mobile implementation: 390 x 844 pixels, 390 x 844 CSS viewport, device scale factor 1.
- The committed source is desktop-only. Mobile was compared for responsive preservation of the source's visual language and against the requested compact geometry, not for fixture-level pixel identity.

State: signed-out production homepage, dark theme, idle analysis form.

## Full-view comparison evidence

- Composition: the production homepage retains its real, intentionally different content while restoring the reference's strong brand/header band and large low-opacity SB behind content.
- Watermark geometry: at desktop the 720px mask is right-offset and begins in the same upper-right visual band as the reference. At mobile the 296.4px mask remains right-offset and intentionally leaves the viewport without an abrupt internal crop.
- Density and hierarchy: the header has a full-height brand row, stronger navigation, balanced account control, and a clean divider. The production hero remains less content-dense than the historical fixture because homepage feature sections are explicitly out of scope.
- Palette and surfaces: ground, text, secondary, muted, cyan, teal, green, and lime remain mapped to the established Sportabase palette. The satin material uses the finished Design Lab's subdued home colors at 0.078 opacity.

## Focused region comparison evidence

- Header: the supplied logo asset remains at 54px desktop and 46px compact. SPORTABASE renders on one line in the computed `Helvetica, Arial, sans-serif` stack with no cut overlay. Navigation has stronger weight and increased spacing without changing destinations.
- Watermark: browser sampling confirmed the outer mark's bounding box and `transform: none` were unchanged across a one-second normal-motion interval while the internal satin transform changed. Under `prefers-reduced-motion: reduce`, the mark and satin transforms both resolved to `none`, leaving the static base material visible.
- No focused image-quality crop was needed because the implementation and reference use the same committed `sportabase-logo.png` mask asset.

## Findings

No actionable P0, P1, or P2 mismatch remains in the requested identity scope.

The production hero copy, form layout, and absence of historical fixture sections remain visibly different from the reference by design. Reconstructing homepage feature sections or fixture content was explicitly excluded.

## Comparison history

1. First implementation capture found a P1 wordmark wrap on the final `E` at desktop and mobile, plus a P2 vertical watermark offset caused by mounting below the production shell header.
2. The wordmark received a non-wrapping line constraint and measured Helvetica lockup widths. The watermark's viewport target now compensates for the web shell header while preserving native coordinates.
3. Post-fix captures show a single-line compact wordmark and desktop watermark alignment comparable to the source. Browser motion sampling and the 1440/390 screenshots provide post-fix evidence.

## Required fidelity surfaces

- Fonts and typography: passed. Helvetica web stack, native platform fallbacks, strong compact uppercase treatment, no Oxanium styling or cut overlay.
- Spacing and layout rhythm: passed. Header height, brand relationship, nav breathing room, divider, and right-offset watermark match the reference language.
- Colors and visual tokens: passed. Established dark ground/surfaces and restrained cyan/teal/green/lime identity are preserved.
- Image quality and asset fidelity: passed. The supplied Sportabase logo asset is used directly as the mask/native image with no replacement artwork.
- Copy and content: passed for scope. Production copy and functionality remain unchanged; historical fixture copy was not restored.
- Responsiveness and accessibility: passed. Browser coverage includes 1440, 768, 390, and 320 widths, no horizontal overflow, 44px target checks, keyboard focus, and reduced motion.

Primary interactions tested: primary navigation, sign-in boundary, analysis sign-in gate, Discover search states, Settings navigation, and route rendering.

Console/error overlay result: no error overlay or blank-page failure was observed in the passing Playwright suite.

Final result: passed
