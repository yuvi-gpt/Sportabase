# Sportabase Expo App — Design Direction

The Expo application is a first-class Sportabase interface and can run as both a mobile application and a browser application.

## Visual character

Sportabase should feel like an evidence and sports-intelligence product, not an AI-generated SaaS dashboard.

The interface should rely on:

- typography;
- spacing;
- alignment;
- information hierarchy;
- restrained borders;
- deliberate density;
- the real Sportabase brand mark.

Avoid:

- giant rounded cards;
- decorative green glow;
- glassmorphism;
- tiny uppercase labels everywhere;
- excessive pill UI;
- card-within-card composition;
- gradients used merely to make important information feel "AI";
- decorative visual effects that do not communicate state.

## Wide-screen behavior

Expo Web must behave like a real desktop application.

The page should use available horizontal space rather than rendering a mobile-width application in the center of the browser.

The analysis workflow becomes a two-column editorial layout on wide screens while remaining a single-column interface on phones.

## Product semantics

Merit is informational Merit, not a truth probability.

Evidence, corroboration and independence remain distinct signals.

Article and YouTube analysis keep separate pipelines while sharing one visual language.

## Functional boundary

This visual pass must not change:

- YouTube transcript acquisition;
- article content resolution;
- Gemini/provider behavior;
- backend API contracts;
- sharing/deep-link behavior;
- analysis semantics.

Result cards are preserved during the first shell checkpoint and will be redesigned separately.
