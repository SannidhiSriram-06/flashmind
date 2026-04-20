# Cuemath Build Challenge — Submission Notes

> Problem chosen: **Problem 1 — The Flashcard Engine**
> GitHub: https://github.com/SannidhiSriram-06/flashmind
> Live URL: [Add Railway URL here]

---

## What Was Built

FlashMind is a full-stack AI flashcard engine. Users sign up, upload a text-based PDF, and receive 10 AI-generated flashcards within ~15 seconds. They then study through a flip-card interface with 3-button SM-2 spaced repetition (Again / Hard / Easy). The app tracks 30 days of study history, calculates streaks and average scores, and schedules each card's next review based on performance.

### Core features shipped:
- **PDF upload + AI card generation** — pdfplumber extracts text; Groq's LLaMA 3.1 generates 10 flashcards as JSON; 3-attempt retry with escalating prompt strictness handles LLM output variability
- **Full SM-2 spaced repetition** — per-card interval, ease factor, repetition count, next_review date stored in MongoDB; 3 quality levels (0/2/5) map to Again/Hard/Easy
- **"Again" card re-queue** — cards rated Again are re-inserted 3–7 positions ahead in the current session queue so they reappear before the session ends
- **Study history + stats** — 30-day bar chart, best streak calculation, easy/hard/again breakdowns, session count
- **Auth system** — signup, login, logout, profile update, password change, account deletion (with password confirmation)
- **Security** — bcrypt passwords, itsdangerous signed session cookies (SameSite=Strict, HttpOnly), per-IP rate limiting on login (10/15min) and upload (5/hour), security headers middleware, no insecure defaults
- **Polished UI** — glassmorphism design system, dark/light theme, particle background, 3D card tilt, card exit animations, view transitions, skeleton loaders, mobile responsive
- **Production deployment** — Railway (nixpacks), MongoDB Atlas, slim requirements-prod.txt (no torch/chromadb)

---

## Key Decisions and Tradeoffs

### FastAPI over Node/Express
FastAPI gives Pydantic-validated request bodies, automatic OpenAPI docs, and Python's data-science ecosystem (pdfplumber, sentence-transformers) in one package. The alternative — Node + Multer + some PDF parser — would have required more glue code for less robust validation. The tradeoff: Python's GIL means CPU-bound PDF processing blocks async routes. Acceptable for a demo; a production app would use a task queue.

### SM-2 over Leitner boxes
Leitner boxes give a binary pass/fail with fixed box intervals (1, 2, 7, 14 days). SM-2 tracks a continuous ease factor per card and adjusts intervals individually based on performance history. A card a user consistently finds Easy gets longer intervals; one they keep getting wrong stays at short intervals. The added complexity (3 floats per card in MongoDB) is worth it for genuinely adaptive scheduling. SM-2 is also the algorithm Anki uses — it's the proven standard.

### Groq (llama-3.1-8b-instant) over OpenAI
Groq's free tier offers ~300 tokens/sec inference speed — significantly faster than OpenAI's free tier, and with no API cost. For a build challenge where the budget is zero, this was the clear choice. The tradeoff: llama-3.1-8b occasionally returns malformed JSON, requiring the 3-attempt retry fallback chain. GPT-4 would be more reliable, but the retry logic handles the variability adequately.

### Railway over Render/Vercel
Render's free tier spins down after 15 minutes of inactivity — the first request after sleep takes 30–60 seconds, which is a terrible demo experience. Railway keeps the app alive on its free tier. Vercel doesn't support long-running FastAPI processes well (5-minute function timeout). Railway with nixpacks auto-detects Python, reads `nixpacks.toml`, and builds cleanly from `requirements-prod.txt`.

### Session cookies over JWT
JWTs stored in localStorage are readable by JavaScript — XSS attacks can steal them. JWTs stored in cookies are functionally equivalent to session cookies but with extra complexity (access + refresh token dance). For a monolithic SPA where all API calls go to the same origin, an HttpOnly SameSite=Strict session cookie signed with itsdangerous is simpler and equally secure. No localStorage, no refresh endpoint, no token expiry handling in the frontend.

### Single HTML SPA over React
A React app requires Node, a bundler (Webpack/Vite), a build step, and a separate deployment for the frontend or a server-side rendering setup. A single `static/index.html` served directly by FastAPI eliminates all of that. The tradeoff: the file is ~1600 lines with CSS and JS inline — harder to maintain at scale. For a solo demo project this was the right call. Zero deployment complexity. Hot reload works via FastAPI's `--reload`.

### DISABLE_VECTOR_STORE in production
ChromaDB + sentence-transformers + torch = approximately 5GB of Docker image. Railway's free tier has a 500MB RAM limit and deploys would OOM during startup. The vector store is still architecturally present — chunks are stored at upload time, queries at review time — but the actual ChromaDB/embedding code is wrapped in a `_DISABLED` guard. Setting `DISABLE_VECTOR_STORE=true` makes all vector store functions no-ops. Groq receives the raw text chunks directly instead. The abstraction layer means re-enabling it for a better-resourced deployment requires only removing the env var.

---

## Challenges Hit and How They Were Solved

### 1. 5.8GB Railway deployment image
**What happened:** `requirements.txt` includes `chromadb`, `sentence-transformers`, and `torch`. The Railway build succeeded but the image was 5.8GB, causing OOM errors at startup on the free tier.

**Fix:** Created `requirements-prod.txt` with only the 10 slim production dependencies (no ML packages). Added `nixpacks.toml` pointing to `requirements-prod.txt`. Set `DISABLE_VECTOR_STORE=true` as a Railway env var so the app doesn't import those packages at runtime either. Production image dropped to under 200MB.

### 2. "Again" cards not reappearing during study sessions
**What happened:** The original implementation tracked study position with `S.shuffled` (array) and `S.idx` (integer). When a card was rated "Again," a copy was spliced into `S.shuffled` — but the position calculation used `findIndex` with text matching, which broke silently when two cards had identical front text. Duplicate cards would update the wrong card state in MongoDB.

**Fix:** Rewrote study state to use `S.queue` (the shuffled array) and `S.queuePos` (current position). At session start, `beginSession()` wraps each card with `_originalIdx: i` — the card's position in the original deck array. All subsequent operations (re-insert, review API call) use `_originalIdx`, not queue position or text content. This makes duplicate-card behavior correct by construction.

### 3. SM-2 Hard formula bug
**What happened:** The Hard (quality=2) branch calculated `interval * 0.8` instead of `interval * ease * 0.8`. This meant Hard reviews ignored the ease factor entirely, making cards with high ease factors progress at the same rate as cards with low ease. Discovered during a code review pass after initial implementation.

**Fix:** Corrected to `max(1, round(interval * ease * 0.8, 2))` in `app/api/decks.py`. The fix is a single multiplication, but getting it right matters for the algorithm's correctness over time.

### 4. Railway DNS not resolving after initial deploy
**What happened:** First Railway deploy completed successfully (green build log) but the generated domain returned a DNS error for ~20 minutes. Railway's free tier can take time to propagate DNS for new projects.

**Fix:** Created a fresh Railway project (different project ID = new domain provisioning). The second project resolved within 2 minutes. The root cause was likely a provisioning hiccup on the first project; creating fresh was faster than debugging it.

### 5. GitHub authentication for git push
**What happened:** After setting up the Railway project and wanting to push the final commit, GitHub rejected the push with "Support for password authentication was removed." The machine hadn't been configured with a PAT or SSH key for this repository.

**Fix:** Generated a Personal Access Token on GitHub with `repo` scope. Used it as the password for HTTPS push. Committed the `nixpacks.toml` and `requirements-prod.txt` fixes in the same push.

---

## What Would Be Improved With More Time

1. **Async PDF processing with job polling** — The upload route currently blocks for the entire PDF parse + Groq call (10–30 seconds). The right pattern is to return `202 Accepted` with a job ID immediately, process in a background task, and let the frontend poll `GET /api/jobs/{id}`. This would eliminate the proxy timeout risk and allow a real progress indicator.

2. **Multi-PDF deck merging** — Real exam prep involves multiple chapters. Being able to upload 3 PDFs and combine them into one deck (with deduplication) would make FlashMind genuinely useful beyond a demo.

3. **AI "Explain more" button** — Post flip, a button that fetches the source chunk from the vector store and asks Groq to elaborate. This is the core use case for ChromaDB being in the architecture already — it's plumbed in, just disabled. With proper hosting (or a lighter embedding model), this feature is one endpoint away.

4. **Heat map calendar** — A GitHub-style contribution calendar showing daily study consistency. More motivating than a 30-day bar chart because it creates the visual "don't break the streak" effect.

5. **Export to Anki (.apkg) or CSV** — Study material should be portable. Anki export would make FlashMind a tool people actually keep using after the demo, not just something they try once.

6. **MongoDB aggregation for stats** — The `/api/stats` endpoint loads all study_sessions into Python memory and aggregates in-app. This should be a `$group` aggregation pipeline query. Fine at demo scale; breaks at production scale.

7. **Achievement badges system** — "7-day streak," "100 cards mastered," "Perfect session." Light gamification proven to increase retention in learning apps.

---

## Submission Links

- **Live URL:** [Add Railway URL here]
- **GitHub:** https://github.com/SannidhiSriram-06/flashmind
- **Google Doc write-up:** [Add link here]
- **Demo video:** [Add link here]
