# Sportabase

## Sports Intelligence, Not Just Sports Summaries

Sportabase is an evidence-first sports intelligence platform for analyzing sports media.

The product is designed to go beyond answering:

"What does this article or video say?"

Sportabase aims to answer:

- What is being claimed?
- Who originated the information?
- What evidence supports it?
- Do independent trusted sources corroborate it?
- How reliable have those sources been historically?
- How has confidence in the story changed over time?
- What can that information movement tell us?

Sportabase currently analyzes sports articles and YouTube videos through a Chrome extension, FastAPI backend, and React Native mobile application.

The long-term goal is to build a persistent sports intelligence system that remembers previously analyzed stories, learns from what eventually happened, and uses those historical information patterns as inputs into future predictive analysis.

---

## Product Model

Sportabase is evolving around this structure:

    Media Piece
        |
        v
    Story / Claim
        |
        v
    Sources + Evidence
        |
        v
    Analysis History
        |
        v
    Score Trajectory
        |
        v
    Alerts + Predictive Signals

A media piece may be:

- a sports article
- a YouTube video
- a social post
- a thread
- a Reddit post
- another supported public sports source

Multiple media pieces may refer to the same underlying story.

An ESPN article, a reporter post, a YouTube report, and an official club statement may all provide evidence about the same transfer story.

Sportabase should eventually connect them rather than treating every URL as an unrelated object.

---

## Current Capabilities

### Chrome Extension

The Sportabase Chrome extension currently supports:

- sports article analysis
- YouTube transcript analysis
- Merit Scores
- TLDR summaries
- article and content classification
- evidence and reasoning signals
- multilingual analysis
- dynamic score-based visual presentation
- caching
- quota and capacity protection

The extension acts as an intelligence overlay on top of the original sports page.

### Mobile Application

The Sportabase mobile application currently supports:

- sharing links into Sportabase
- manually pasting article links
- manually pasting YouTube links
- article content resolution
- article analysis
- YouTube transcript analysis
- Merit Score results
- score explanations
- content-type confidence
- score-responsive visual themes

The mobile application is being redesigned around dedicated media and story pages, History, tracking, notifications, settings, and richer analysis views.

### Backend

The FastAPI backend currently handles:

- article and video analysis
- content resolution
- Merit Score calculation
- content classification
- language detection
- Gemini-assisted analysis
- caching
- usage accounting
- request capacity controls

SQLite is currently used for persistence.

---

# Merit Score

The Merit Score is a 0-100 assessment of how strongly a piece of sports reporting is supported by the available evidence.

It is not intended to be an absolute truth detector.

A score should be capable of changing as the real-world information environment changes.

Examples:

- new evidence appears
- another trusted outlet independently corroborates the claim
- an official source confirms the story
- an official source denies the story
- conflicting reporting appears
- a reporter corrects or retracts information
- the underlying story develops

The Merit Score should therefore become a time-dependent intelligence signal rather than a static article rating.

---

# Merit Score vNext

The next scoring system will place substantially more weight on external evidence, source history, and corroboration.

## 1. Publisher Reputation

Sportabase should evaluate the publication making the claim.

Signals may include:

- historical reporting accuracy
- correction rate
- retraction rate
- transparency
- primary-report frequency
- independence from other reporting
- evidence quality
- topic-specific historical accuracy
- publication history
- domain or publication age as a low-weight supporting signal

Site age alone should never make a publication trustworthy.

Historical behavior should matter far more.

---

## 2. Reporter Reputation

Where a named journalist or reporter is identifiable, Sportabase should track their historical record separately from the publication.

Possible signals include:

- previous claims tracked
- eventual confirmation rate
- correction rate
- retraction rate
- topic-specific reliability
- primary-source frequency
- speed versus accuracy

A reporter may be highly reliable in one area of sport and less reliable in another.

---

## 3. Evidence Quality

Sportabase should evaluate what evidence is actually presented.

Possible evidence includes:

- official club statements
- league statements
- press releases
- regulatory documents
- direct quotations
- named sources
- attributed anonymous sources
- interviews
- press conferences
- statistics
- photographs
- video
- first-hand reporting
- links to primary evidence

Confident writing should never substitute for actual evidence.

---

## 4. Evidence Investigation

Sportabase should eventually investigate the evidence cited by a media piece rather than only detecting that a source exists.

For example:

    Article
      -> Reporter
          -> Anonymous Source

is materially different from:

    Article
      -> Official Club Statement

The system should increasingly identify:

- original source
- intermediaries
- primary evidence
- secondary reporting
- unsupported claims
- circular sourcing

---

## 5. Independent Corroboration

Independent corroboration should become one of the strongest Merit Score signals.

Sportabase should determine whether unrelated trustworthy sources independently support the same underlying claim.

Three independent reputable reports are meaningful.

Ten websites rewriting the same original report are not ten confirmations.

This requires:

- story clustering
- origin tracing
- duplicate-content detection
- source-dependency detection
- copied-reporting detection
- churnalism detection

Sportabase should measure independent evidence, not raw article volume.

---

## 6. Specificity

Specific reporting is easier to verify or disprove.

Relevant signals include:

- named players
- named teams
- dates
- transfer values
- contract lengths
- locations
- competition details
- named sources
- attributed quotations
- clearly defined events

Specificity improves testability.

It does not prove that a claim is true.

---

## 7. Language and Claim Strength

Language remains useful, but it should only be one part of legitimacy.

Sportabase currently detects signals such as:

- reportedly
- could
- might
- believed to
- expected to
- sources say
- set to
- official
- confirmed
- announced
- sensational framing
- clickbait
- opinion framing

Language helps answer:

"How strongly is this source presenting the claim?"

It does not answer:

"Is the claim actually true?"

---

## 8. Content-Type Fit

Different sports content requires different standards.

Examples include:

- transfer rumor
- confirmed transfer
- injury report
- match report
- tactical analysis
- statistics report
- press conference
- opinion article
- official announcement
- legal or disciplinary report

A transfer rumor should not be evaluated using the same expectations as an official club announcement.

---

## 9. Temporal Context

Sportabase should understand where a report sits in the development of a story.

A story may progress through states such as:

    Initial Rumor
        ->
    Developing
        ->
    Corroborated
        ->
    Advanced
        ->
    Confirmed

Other stories may instead move toward:

    Reported
        ->
    Contradicted
        ->
    Denied

or:

    Reported
        ->
    Corrected
        ->
    Retracted

The score should reflect these developments.

---

# Persistent History

Sportabase will store analyzed public sports media so that previous analysis can improve future analysis.

The system should distinguish between the exact media item and the underlying story.

## Media Item

A media item represents the exact content analyzed.

Possible stored information includes:

- canonical URL
- publisher
- reporter
- publication timestamp
- content hash
- content type
- first analyzed timestamp
- latest analyzed timestamp

## Story

A Story represents the underlying real-world claim or event.

For example:

"Barcelona attempting to sign Player X"

Multiple media items may belong to the same Story.

---

# Analysis Snapshots

Each meaningful analysis should create an immutable historical snapshot.

Example:

    10:00    Merit 31
    12:20    Merit 48
    15:40    Merit 63
    18:10    Merit 78
    21:35    Merit 96

Each snapshot should preserve:

- Merit Score
- scoring components
- source reputation
- reporter reputation
- available evidence
- corroborating sources
- classification
- uncertainty
- timestamp
- scoring-engine version

The scoring-engine version is essential.

An algorithm update must not be mistaken for a real-world credibility movement.

---

# Story Trajectory

Historical snapshots allow Sportabase to measure how information changes over time.

For example:

    31 -> 48 -> 63 -> 78 -> 96

Sportabase should also explain why the score changed.

Example:

    31
    Initial speculative report

    48
    Reliable reporter independently confirms talks

    63
    Second trusted outlet corroborates the story

    78
    Multiple independent reports indicate an agreement

    96
    Official club announcement

This creates a new concept:

## Information Momentum

Possible future signals include:

- Merit Score velocity
- Merit Score acceleration
- corroboration velocity
- evidence growth
- contradiction rate
- source-quality improvement
- news-volume growth
- story-state transitions

Sportabase should eventually be able to answer:

"How quickly is the evidence around this story strengthening or weakening?"

---

# History

The mobile application will include a History section containing media and stories previously analyzed by the user.

Users should eventually be able to reopen an item and view:

- current Merit Score
- previous Merit Scores
- score trajectory
- source changes
- evidence changes
- corroboration changes
- story status
- analysis timestamps

---

# Story Tracking and Movement Alerts

Users should be able to track stories they care about.

Sportabase should notify them when meaningful movement occurs.

Potential notification triggers include:

- large Merit Score increase
- large Merit Score decrease
- crossing a score band
- major new independent corroboration
- official confirmation
- official denial
- major contradiction
- correction
- retraction

Small score fluctuations should not generate notifications.

Example:

    Major movement

    Rodri -> Barcelona
    Merit Score: 42 -> 68 (+26)

    New independent reporting and stronger
    source evidence increased confidence.

---

# Shared Sports Intelligence Corpus

Public sports media analyzed through Sportabase can contribute to a growing intelligence database.

Over time the corpus can contain:

- publishers
- reporters
- media items
- stories
- claims
- source relationships
- evidence chains
- historical scores
- confirmations
- denials
- corrections
- retractions
- eventual outcomes

This historical database can help Sportabase make more informed decisions on future stories.

For example:

    Reporter A

    Transfer claims tracked: 184
    Eventually confirmed: 151
    Historical reliability: High

Historical performance should influence future assessments probabilistically rather than act as absolute truth.

Personal user information should remain separate from the shared public-media intelligence corpus.

---

# Predictive Intelligence

The Merit Score itself is not intended to predict match or market outcomes.

Instead, historical information movement can become one input into a broader predictive system.

Future predictive analysis may combine:

    Information momentum
    +
    Story credibility trajectory
    +
    News volume
    +
    Source quality
    +
    Sentiment
    +
    Team and player context
    +
    Historical performance
    +
    Market or betting movement
    +
    Structured sports data

This may eventually allow Sportabase to investigate questions such as:

"Is the market reacting faster than the available evidence supports?"

or:

"Is strong credible information appearing before the market has meaningfully reacted?"

This forms the basis of Sportabase's future market-overreaction research.

---

# Planned Backend Architecture

The backend is expected to evolve toward entities such as:

- sources
- reporters
- media_items
- stories
- claims
- story_media_links
- evidence_items
- source_relationships
- analysis_snapshots
- score_events
- user_history
- tracked_stories
- alerts

Entity resolution will later connect:

- players
- teams
- clubs
- leagues
- competitions
- countries
- reporters
- publishers
- YouTube channels
- social accounts

---

# Evaluation

A more sophisticated scoring engine requires stronger regression testing.

Sportabase will maintain a golden-set evaluation harness containing examples such as:

- weak rumors
- strong rumors
- confirmed transfers
- false reports
- official announcements
- opinion pieces
- match reports
- multilingual articles
- misleading headlines
- copied coverage

Every major scoring change should be tested against the golden set.

---

# Development Roadmap

## Phase 1 - Data and History Foundation

- expand the database schema
- canonicalize media URLs
- store analyzed public media
- create analysis snapshots
- version the scoring engine
- create source records
- create reporter records
- preserve score history

## Phase 2 - Merit Score vNext

- historical publisher accuracy
- historical reporter accuracy
- independent corroboration
- evidence investigation
- source provenance
- copied-reporting detection
- stronger evidence scoring
- reduced dependence on language heuristics
- uncertainty and confidence
- exposed score components

## Phase 3 - Story Intelligence

- entity resolution
- claim extraction
- story clustering
- evidence relationships
- source dependency detection
- cross-source corroboration
- story state tracking

## Phase 4 - Story Trajectory

- score deltas
- evidence deltas
- corroboration deltas
- credibility timelines
- information momentum

## Phase 5 - Tracking and Alerts

- story watchlists
- significant-movement detection
- confirmation alerts
- denial alerts
- contradiction alerts
- mobile notifications

## Phase 6 - Frontend Productization

- dedicated Home screen
- dedicated media screens
- dedicated story screens
- History
- trajectory charts
- Dark / Light / System themes
- settings
- watchlists
- richer evidence views

## Phase 7 - Predictive Intelligence

- combine story trajectories with structured sports data
- quantify market reaction
- test market-overreaction hypotheses
- evaluate predictive performance against historical outcomes

---

# Technical Stack

## Backend

- Python 3.14.7
- FastAPI
- SQLite
- Requests
- Gemini
- local rule-based analysis
- caching
- usage and quota controls

## Browser Extension

- JavaScript
- Chrome Extension APIs
- in-page intelligence overlay
- article extraction
- YouTube transcript extraction

## Mobile

- React Native
- Expo
- Expo Router
- TypeScript

## Infrastructure

- Render
- GitHub
- GitHub Pages

---

# Development Principles

## Evidence over confidence

Confident writing is not evidence.

## Independent corroboration over repetition

Ten copies of one report are not ten confirmations.

## History over static reputation

Credibility should increasingly come from observable historical performance.

## Explainability over black-box scoring

Users should understand why a score exists and why it changed.

## Stories over URLs

Multiple media pieces may describe the same underlying event.

## Trajectory over snapshots

How information changes can be as important as its current state.

## Probability over certainty

Sportabase evaluates evidence. It does not claim omniscience.

---

# Final Vision

Sportabase aims to become an intelligence layer for global sports information.

Not merely:

"Summarize this story."

But:

- What is being claimed?
- Who originated it?
- What evidence supports it?
- Who independently corroborates it?
- How reliable have those sources historically been?
- How has confidence changed over time?
- What does that information movement imply?

The long-term objective is a system that remembers sports information, learns from what eventually happened, and uses that history to make progressively better evidence-based assessments.

**Sportabase - Understand the story, not just the headline.**
