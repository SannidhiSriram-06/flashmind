# FlashMind — AI Flashcard Engine | Cuemath Build Challenge
### Write-up — ready to paste into Google Doc

---

## What I Built

The problem I chose was Problem 1: The Flashcard Engine. I built FlashMind — a web application that turns any PDF into a study-ready flashcard deck using AI, then reviews those cards through a spaced-repetition algorithm that schedules each card at the scientifically optimal interval.

The core user journey is three steps: upload a PDF, study the AI-generated cards, repeat on schedule. When you upload a PDF, pdfplumber extracts the text and splits it into overlapping 500-character chunks. Those chunks are sent to Groq's LLaMA 3.1 model, which generates exactly 10 flashcards as structured JSON. The cards are saved to MongoDB with per-card spaced repetition state, and you're immediately taken to a study session. Each card flips to reveal its answer, and you rate your recall with one of three buttons — Again, Hard, or Easy. The SM-2 algorithm uses your response to compute when you should see that card again, ranging from tomorrow for "Again" to weeks later for cards you consistently find Easy.

The full feature set includes: user accounts with bcrypt-hashed passwords and signed session cookies; per-IP rate limiting on both login and upload; a polished glassmorphism UI with dark/light theme; mobile responsive layout; 30-day study history with bar charts and streak tracking; card exit animations, view transitions, skeleton loaders; and a single-file SPA deployed to Railway with MongoDB Atlas.

---

## Key Decisions & Tradeoffs

### FastAPI over Node/Express
FastAPI gives Pydantic request validation, automatic OpenAPI docs, and access to Python's data ecosystem (pdfplumber, sentence-transformers) in one package. The alternative would have required significantly more glue code for PDF handling and JSON validation. The tradeoff is Python's GIL — CPU-bound PDF processing blocks async routes. For a demo with low concurrency, this is acceptable.

### SM-2 over Leitner Boxes
Leitner boxes use fixed intervals (1, 2, 7, 14 days) with binary pass/fail. SM-2 tracks a continuous ease factor per card — a card you find Easy repeatedly gets exponentially longer intervals; one you keep forgetting stays short. The added complexity (3 floats per card in MongoDB) is worth it for genuinely adaptive scheduling. SM-2 is the algorithm Anki uses, and it's the proven standard for spaced repetition.

### Groq (llama-3.1-8b-instant) over OpenAI
Groq's free tier delivers ~300 tokens/second inference — significantly faster than OpenAI's free tier, with no cost. For a build challenge with a zero budget, this was the clear choice. The tradeoff: llama-3.1-8b occasionally returns malformed JSON (markdown fences, trailing prose). I handled this with a 3-attempt retry chain using escalating system prompts: standard → strict → raw-JSON-fallback. This covers the vast majority of LLM output variability.

### Railway over Render/Vercel
Render's free tier spins down after 15 minutes of inactivity — the first request wakes it up in 30–60 seconds, which kills a demo. Railway keeps containers alive on its free tier. Vercel doesn't support long-running FastAPI processes well (5-minute function timeout, no persistent filesystem). Railway with nixpacks auto-detects Python, reads `nixpacks.toml`, and builds from `requirements-prod.txt` with zero extra configuration.

### Session Cookies over JWT
JWTs in localStorage are readable by JavaScript — any XSS vulnerability exposes them. For a monolithic SPA where all API calls go to the same origin, an HttpOnly SameSite=Strict session cookie signed with `itsdangerous.TimestampSigner` is simpler and equally secure. No access + refresh token dance, no token expiry logic in the frontend, no localStorage. The session cookie expires in 7 days and cannot be read or forged by client-side code.

### Single HTML SPA over React
A React app requires Node.js, a bundler, a build step, and either a separate static host or server-side rendering setup. A single `static/index.html` served by FastAPI's `StaticFiles` eliminates all of that. Hot reload works via FastAPI's `--reload`. The tradeoff: the file is ~1600 lines of inline CSS and JS — harder to maintain at scale. For a solo 3-day build, eliminating the build pipeline was the right call.

### DISABLE_VECTOR_STORE in production
ChromaDB + sentence-transformers + PyTorch = ~5GB Docker image. Railway free tier has 500MB RAM. The solution: wrap all vector store operations behind a `_DISABLED` environment flag that makes them no-ops. The abstraction is still fully built — chunks are stored at upload time, semantic queries are available — just dormant in production. Re-enabling it for a better-resourced deployment requires removing one env var.

---

## Interesting Challenges

### The 5.8GB image problem
My first Railway deployment built successfully, then OOM-crashed at startup. The cause: `requirements.txt` included `chromadb`, `sentence-transformers`, and `torch` — the ML stack needed for local vector search. I created a separate `requirements-prod.txt` with only the 10 slim dependencies needed at runtime, pointed `nixpacks.toml` at it, and added `DISABLE_VECTOR_STORE=true`. Production image dropped from 5.8GB to under 200MB. The lesson: keep your dev and production dependency graphs separate from day one.

### The "Again" card bug
The first implementation of the study loop used `findIndex` with text matching to find a card's position before re-inserting "Again" cards into the queue. This worked until I tested with two cards that had identical front text — the wrong card's MongoDB state was being updated. The fix was to attach `_originalIdx` to each queue item at session start (the card's position in the original deck array) and use that for all backend calls. Now re-queued "Again" copies carry their original index through every shuffle and splice, making duplicate-card behavior correct by construction.

### SM-2 formula error
The Hard (quality=2) branch originally calculated `interval * 0.8`, missing the ease factor multiplication. The correct formula is `interval * ease * 0.8`. This meant a card with an ease of 2.5 progressed at the same rate whether you hit Hard or Easy — defeating the purpose of the algorithm. Found it during a systematic code review pass, not through testing. The fix was one multiplication added, but it would have produced subtly wrong scheduling data for every Hard-rated review if it had shipped.

### Railway DNS provisioning hiccup
My first Railway project deployed (green build log, app running) but the generated domain returned DNS errors for 20+ minutes. Rather than wait, I created a fresh Railway project. New project ID triggered new domain provisioning, which resolved within 2 minutes. The first project likely had a provisioning hiccup on Railway's infrastructure — a fresh project was faster than debugging it.

### LLM output variability
Groq's LLaMA 3.1 doesn't always return clean JSON. In testing it returned: JSON wrapped in triple-backtick markdown fences; JSON with a prose paragraph before it; 8 cards instead of 10; `"question"/"answer"` keys instead of `"front"/"back"`. The solution was a three-attempt retry chain. Attempt 1 uses the standard prompt. If JSON parsing fails, Attempt 2 uses a stricter prompt ("Output ONLY a valid JSON array, no markdown"). If that fails, Attempt 3 uses a raw instruction ("Start your response with [ and end with ]"). This handles real-world LLM output variability without crashing.

---

## What I'd Improve With More Time

1. **Async PDF processing with job polling** — The upload route currently blocks for 10–30 seconds while Groq responds. The right pattern is `202 Accepted` + job ID immediately, background processing, polling endpoint. This eliminates the proxy timeout risk and allows a real progress bar.

2. **AI "Explain more" button** — After flipping a card, a button that pulls the source PDF chunk from the vector store and asks Groq for a detailed explanation. ChromaDB is already in the architecture — it's just disabled. With proper hosting, this feature is one endpoint away and would make FlashMind significantly more useful as a study tool.

3. **Export to Anki (.apkg) or CSV** — Study material should be portable. Anki export in particular would let users take their AI-generated decks into their existing study workflow.

4. **Heat map calendar** — A GitHub-style contribution graph for daily study consistency. More motivating than a bar chart because the "don't break the streak" visual effect is proven to drive daily habit formation.

5. **Multi-PDF deck merging** — Real exam prep involves multiple chapters. Uploading several PDFs into one deck would make the app useful for full-course revision, not just single-document study.

---

## Technical Stack

| Component | Technology | Why |
|---|---|---|
| **Web framework** | FastAPI (Python 3.11) | Pydantic validation, async, Python data ecosystem |
| **Frontend** | Vanilla JS/CSS in a single HTML file | Zero build pipeline, FastAPI-served SPA |
| **LLM** | Groq API — llama-3.1-8b-instant | Free tier, ~300 tok/s, sufficient quality for flashcard generation |
| **PDF parsing** | pdfplumber | Robust text extraction, handles multi-column layouts |
| **Database** | MongoDB Atlas (pymongo) | Schemaless card_states map, free tier, simple driver |
| **Auth** | bcrypt + itsdangerous TimestampSigner | bcrypt for passwords, signed cookie sessions without a session store |
| **Vector store** | ChromaDB + all-MiniLM-L6-v2 | Semantic chunk retrieval (disabled in prod, ready for "Explain more") |
| **Deployment** | Railway via nixpacks | No sleep-on-inactivity, auto-detects Python, clean nixpacks.toml config |
| **Building partner** | Claude Code (Anthropic) | Used as an AI pair programmer throughout the build — flagged bugs, reviewed security, suggested architectural patterns, wrote and refactored code iteratively |
