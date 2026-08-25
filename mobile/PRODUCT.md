# Sportabase Product Context

Sportabase is an evidence-first sports intelligence product.

A user supplies one source URL.

Sportabase determines what kind of source it is and routes it through the correct
analysis pipeline automatically.

Current first-class source types:

- sports article
- YouTube video

The user does not choose Article mode or Video mode.

Source type is an implementation detail.

## Core hierarchy

Sportabase should help answer:

1. What is this source actually claiming?
2. How much informational Merit does the reporting have?
3. What does the available evidence support?

Merit is not a probability of truth.

Evidence status is separate from Merit.

No corroboration does not mean false.

## Product character

Sportabase should feel:

- editorial
- analytical
- sports-native
- independent
- fast
- authored

It should not feel:

- like an AI chatbot
- like a generic SaaS landing page
- like a neon dashboard
- like a component-library showcase
- like a page assembled from rounded cards

## Interaction

One URL field.

One Analyze action.

Sportabase detects YouTube internally and uses the video pipeline.

Other supported URLs are resolved through the article pipeline.
