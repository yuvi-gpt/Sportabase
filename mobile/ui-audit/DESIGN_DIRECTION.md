# Sportabase Expo App - Unified Source Boundary

The Expo application now uses one source field and one Analyze action.

The interface does not ask the user to select Article or Video.

Routing is automatic:

- YouTube URL -> transcript acquisition -> video analysis
- other supported HTTP(S) URL -> content resolution -> article analysis

The user sees one workflow.

## Visual framework

The previous hero-plus-tool-card layout is retired.

The application now uses:

- editorial lead typography
- full-width source workspace
- thin structural rules
- restrained green signal accents
- report-oriented information architecture
- wider desktop composition
- responsive mobile composition

The design intentionally avoids:

- floating tool cards
- mode tabs
- decorative gradients
- green glow
- nested rounded containers
- component-library dashboard framing

## Functional invariants

This redesign preserves:

- article resolution
- article analysis
- automatic YouTube transcript acquisition
- automatic YouTube title acquisition
- video analysis
- share/deep-link input
- API health state
- provider behavior
- backend API contracts

Article and video result components are redesigned in the next checkpoint.
