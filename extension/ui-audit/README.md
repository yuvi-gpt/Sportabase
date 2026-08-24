# Sportabase Frontend Visual Audit

This directory freezes the pre-redesign Sportabase interface so frontend changes can be evaluated against a real baseline rather than memory or aesthetic guesswork.

## Current architecture

Sportabase remains a modular vanilla-JavaScript Chrome extension bundled with esbuild.

The frontend redesign does not require a React migration.

React-oriented component libraries may be studied for layout and interaction ideas without importing their framework architecture.

## Tooling

### Impeccable

Run:

    npm run ui:detect

The detector scans the current `src/` tree for UI implementation and design anti-patterns.

Exit code `2` means findings were detected and is expected during an audit.

The frozen detector output is stored in:

    impeccable-baseline.txt

### Playwright

Run:

    npm run ui:baseline

The baseline harness launches Playwright's bundled Chromium with a persistent browser context, side-loads a temporary copy of the Manifest V3 extension, and injects Sportabase into deterministic local article and YouTube-style fixtures.

The production manifest is never modified.

No Sportabase backend or Gemini request is made by this visual baseline.

## Frozen screenshots

- `baseline/article-landing.png`
- `baseline/article-settings.png`
- `baseline/video-landing.png`

These images represent the interface before the visual redesign.

They are evidence, not design targets.

## Redesign principle

Sportabase is primarily an intelligence reading and operating surface.

The redesign should prioritize:

- editorial hierarchy;
- evidence clarity;
- restrained use of containers;
- deliberate typography;
- legible information density;
- consistent interaction states;
- meaningful rather than decorative motion;
- clear distinction between Merit, evidence status, article type, and supporting reasoning.

The target is not "a prettier AI dashboard."

The target is a recognizably authored sports-intelligence product.
