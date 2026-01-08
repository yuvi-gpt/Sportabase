# 🧠 Sportabase – AI Sports News Intelligence Engine

## 📌 Overview
**Sportabase** is an AI-driven sports intelligence platform that ingests verified news from trusted sources across multiple sports — football, cricket, NBA, NFL, NHL, MLB, and more — and transforms raw content into structured, scored, and summarized insights.

It filters news based on **fan allegiances** (clubs, leagues, countries, players), **evaluates articles on their factual merit**, generates **concise TL;DR summaries with supporting evidence**, and delivers **personalized voice briefings** — all while remaining legally compliant and attribution-friendly.

---

## 🎯 Goals
- 🧠 Build a **"sports brain layer"** that critically evaluates content rather than just aggregating it.
- 📊 Score articles on **merit, originality, evidence, relevance, and impact**.
- ✂️ Generate transparent **TL;DR summaries** that expose fluff and highlight substance.
- 🏷️ Auto-tag stories by team, league, player, and country using Wikidata.
- 🗣️ Deliver **voice briefings** and summaries tailored to user allegiances.
- ⚖️ Start with a **hybrid model** (external links + AI insights) and evolve into a full **destination platform**.

---

## 🪜 Development Phases

### Phase 0 – Proof of Concept (2–4 weeks)
Minimal version that’s still resume-worthy:
- Fan allegiance setup (teams, leagues, players).
- RSS ingestion from ~10 trusted sources.
- Basic tagging (team, league, sport).
- Extractive TL;DR summaries.
- Merit scoring v1 (fact density + originality).
- External links to original articles.

✅ *Goal:* A GitHub repo, demo video, and README explaining the system.

---

### Phase 1 – Smart Layer + Utility (6–12 weeks)
Turn the MVP into something people actually use daily:
- Hype vs substance scoring.
- Sentiment/vibe meter.
- Daily digest via email or notifications.
- "New vs Recap" detection.
- Voice summaries (browser-based TTS/STT).

---

### Phase 2 – Destination + Insight (3–6 months)
Transform Sportabase into a full-fledged sports intelligence platform:
- Historical analytics (spending, injuries, sentiment trends).
- "What changed since yesterday?" delta views.
- Structured, queryable knowledge base.
- Coverage trend analytics and sentiment graphs.
- AI-driven source discovery.
- Browser extension + mobile app.

---

## 📊 Merit Scoring Framework

Each article is scored (0–100) based on:

| Metric | What It Measures | How |
|--------|------------------|-----|
| 📊 **Factual Density** | Presence of numbers, dates, quotes, named entities | Entity extraction & counting |
| 🆕 **Originality** | % of new info vs prior coverage | Entity/date comparison |
| 📜 **Evidence Quality** | Are claims supported by quotes, press releases, multiple sources? | Regex + metadata |
| 🎯 **Relevance** | Strength of connection to selected teams/leagues | Alias & entity matching |
| 📈 **Impact** | Does it materially change the story (result, injury, signing)? | Context classifier |

---

## ✂️ TL;DR Engine
- Uses extractive summarization first (bullet points + key facts).
- Highlights supporting sentences for transparency.
- Badges thin or speculative content as "Low Substance".
- Displays hype vs substance meter.
- Optional abstractive layer later for polish.

---

## 🧬 Fan Allegiance Layer
Users choose:
- 🏟️ Clubs and national teams  
- 🏆 Leagues  
- 🧑‍🎤 Favorite players  
- 📌 Optional topics (transfers, tactics, injuries)

All content is filtered, ranked, and summarized based on this "fan DNA."

---

## 🏟️ Hybrid News Model
- TL;DR, merit score, vibe meter, tags, and key facts shown on Sportabase.  
- Original articles linked externally.  
- Short quotes/snippets embedded under fair use.  
- Future: analytics, comparisons, and historical context to keep users inside the platform.

---

## 📱 Story Card Example

**📰 Arsenal signs João Neves for £85M**  
Merit Score: 86/100 🧠 Substance: ████████░░ 82%  
Source: BBC Sport · 2h ago Mood: 😄 Positive (73/100)

**TL;DR:**
- Arsenal completes £85M signing of João Neves from Benfica.  
- 5-year deal through 2030.  
- Arteta: "Future of our midfield."  
- Benfica nets record sale.

**Why it matters:** Arsenal breaks its transfer record and strengthens midfield depth.  
📊 Coverage spike: 14 articles (+230%)  
📈 Confirmed by: 5 outlets  
🗣️ Listen | 📚 History | 🔗 [Read Full Story →](#)

---

## 🗣️ Voice Integration
- 3-minute morning/evening briefings across chosen teams.  
- Voice commands: "Next," "Details," "Translate," "Only transfers."  
- Optional multilingual support.

---

## ⚙️ Tech Stack (100% Free-Tier Possible)
- **Backend:** Python + FastAPI  
- **Scraping:** Requests, BeautifulSoup, feedparser  
- **AI:** Hugging Face small models, Gemini/OpenAI free tier, VADER/TextBlob  
- **Data:** JSON or SQLite (start) → PostgreSQL (later)  
- **Frontend:** HTML/CSS/JS → React (later)  
- **Hosting:** Render (backend), Vercel (frontend)  
- **Knowledge Graph:** Wikidata SPARQL

---

## ⚖️ Legal & Ethical Guardrails
- Respect `robots.txt` and avoid paywalled scraping.  
- Summarize and link rather than republishing full text.  
- Prominently display original source names and links.  
- Use AI for analysis, not duplication.

---

## 📈 Final Vision
Sportabase evolves from a smart layer into the **AI brain for global sports news** — contextualizing stories, exposing fluff, surfacing trends, and delivering intelligence tailored to user allegiances.

- 📊 Not a meme page — an **analysis engine**.  
- 🧠 Not a news site — an **insight layer**.  
- 🗣️ Not a feed — a **briefing**.

> "The AI that reads every sports page so you don’t have to."

---

## 📄 Resume-Ready Line
**Sportabase – AI Sports News Intelligence Engine:** Built a multi-source scraper and NLP pipeline that ingests verified sports articles, scores them for factual merit and novelty, auto-tags them by team and league, and generates TL;DR summaries and voice briefings personalized to fan allegiances.
