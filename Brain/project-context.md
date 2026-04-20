# FlashMind — Project Context

> Living context file. Keep this updated as the project evolves.
> Last updated: 2026-04-21

---

## What FlashMind Is

FlashMind is an AI-powered flashcard engine. A user uploads any text-based PDF — lecture notes, a research paper, a textbook chapter — and the app generates 10 targeted flashcards from it in under 30 seconds. Cards are then reviewed through a 3-button spaced-repetition interface (Again / Hard / Easy) that schedules each card for the optimal future review using the SM-2 algorithm. Study history, streaks, and performance stats are tracked over 30 days.

### The Problem It Solves

Students spend hours manually creating flashcards from study material. Existing tools (Anki, Quizlet) require manual card creation; AI wrappers that do exist are either expensive, generic, or buried in subscription paywalls. FlashMind automates the entire extraction-to-study pipeline in a single upload, with spaced repetition baked in from day one.

---

## Tech Stack and Why Each Was Chosen

| Technology | Role | Why chosen |
|---|---|---|
| **FastAPI** | Web framework | Auto-generates OpenAPI docs, native async support, Pydantic validation, production-grade. Faster to write correct code than Flask. |
| **MongoDB Atlas** | Database | Schemaless — card_states nested map grows dynamically per card without schema migrations. Free tier covers demo load. pymongo is straightforward. |
| **Groq (llama-3.1-8b-instant)** | LLM | Free tier, ~300 tokens/sec (fastest inference available), llama-3.1-8b is strong enough for flashcard generation. OpenAI would have cost money. |
| **pdfplumber** | PDF parsing | More reliable text extraction than PyMuPDF for complex layouts; handles multi-column. Actively maintained. |
| **bcrypt + itsdangerous** | Auth | bcrypt for proper password hashing (constant-time comparison). itsdangerous TimestampSigner for tamper-proof, expiring session tokens without a session store. |
| **ChromaDB + all-MiniLM-L6-v2** | Vector store | Enables semantic search over PDF chunks (foundation for future "Explain more" feature). Disabled in prod via env flag to avoid 5GB ML dependency image. |
| **Vanilla JS / Single HTML** | Frontend | No build pipeline. `static/index.html` contains all CSS and JS. Hot-reloads with FastAPI's `--reload`. Zero deployment complexity for the SPA. |
| **Railway (nixpacks)** | Deployment | nixpacks auto-detects Python, uses `nixpacks.toml` to target `requirements-prod.txt`. Better DX than Render for first deploy; no sleep on inactivity. |

---

## Key Architectural Decisions

### 1. Single-file SPA (no React, no bundler)
All UI is in `static/index.html`. Tradeoff: harder to maintain at scale, but eliminates build pipeline complexity entirely. The file is large (~1600 lines) but organized with ASCII section headers. For a solo demo project this was the right call.

### 2. Session cookies over JWT
`itsdangerous.TimestampSigner` creates a signed, expiring cookie. No refresh-token dance, no localStorage, no XSS attack surface for token theft. The cookie is HttpOnly + SameSite=Strict. JWTs would have added complexity with no benefit for a monolithic app.

### 3. DISABLE_VECTOR_STORE in production
ChromaDB + sentence-transformers + torch = ~5GB Docker image. Railway/Render free tiers have tight memory. The vector store is architecturally present (stores embeddings at upload time, queries at review time) but disabled via `DISABLE_VECTOR_STORE=true`. Flashcard generation uses full text chunks directly via Groq instead. This keeps the production image under 200MB.

### 4. Three-attempt LLM retry with escalating prompts
Groq's LLaMA 3.1 occasionally wraps JSON in markdown fences or adds prose. Rather than parse markdown, the app retries with progressively stricter system prompts: standard → strict ("Output ONLY a JSON array") → fallback ("Start with [, end with ]"). This handles ~99% of real-world LLM output variation.

### 5. SM-2 with 3 quality levels (not 6)
Classic SM-2 uses quality 0–5. FlashMind maps this to 3 buttons: Again (0), Hard (2), Easy (5). This is simpler for users (fewer choices = faster reviews) while preserving the algorithm's core behavior. The intermediate Hard button at quality=2 uses `interval × ease × 0.8` to progress slower than Easy.

### 6. `_originalIdx` for SM-2 card identification
When a study session begins, cards are shuffled into `S.queue`. Each queue item stores `_originalIdx` (its position in the original deck array). The review API call always uses `_originalIdx`, not the queue position. This means duplicate front/back cards and "Again" re-inserts both work correctly — the backend always updates the right card state.

### 7. In-memory rate limiting (no Redis)
Both upload (5/hour/IP) and login (10/15min/IP) rate limiters use `defaultdict(list)` with sliding time windows. Simple, dependency-free, sufficient for demo scale. The limitation: doesn't survive restarts and doesn't scale across multiple workers. Acceptable for a single-worker demo deployment.

---

## Current Deployment Status

- **Platform:** Railway (via nixpacks, using `nixpacks.toml` → `requirements-prod.txt`)
- **Live URL:** [Add your Railway URL here]
- **GitHub:** https://github.com/SannidhiSriram-06/flashmind
- **Database:** MongoDB Atlas (M0 free cluster)
- **Vector store:** DISABLED in production (`DISABLE_VECTOR_STORE=true`)
- **Workers:** 1 (Uvicorn single worker — sufficient for demo)

### Env vars set in Railway
- `MONGODB_URI` — Atlas connection string
- `GROQ_API_KEY` — Groq API key
- `SECRET_KEY` — 64-char random hex
- `ENV=production`
- `DISABLE_VECTOR_STORE=true`
- `CORS_ORIGINS` — Railway app domain

---

## Known Limitations

1. **PDF upload is synchronous** — user waits 10–30s for Groq to respond. No progress streaming. With a slow Groq response, Railway's proxy can timeout. Mitigation: `DISABLE_VECTOR_STORE=true` removes embedding time; Groq is usually fast.

2. **In-memory rate limiter resets on restart** — each Railway redeploy resets IP windows. Acceptable for demo, not for production.

3. **10 cards fixed per PDF** — the Groq prompt requests exactly 10. Some PDFs deserve more; some get redundant cards if content is thin. A future version should make card count configurable.

4. **Image-only PDFs not supported** — pdfplumber can only extract selectable text. Scanned PDFs need OCR pre-processing (e.g., `ocrmypdf`) before upload.

5. **Stats endpoint loads all sessions into Python** — aggregation is done in Python not MongoDB. Will slow as data grows. Should use `$group` aggregation pipeline.

6. **No CSRF protection** — `SameSite=Strict` cookie mitigates the main risk, but a proper double-submit CSRF token is not implemented.

---

## Future Improvements (Prioritized)

1. **Async PDF processing with job polling** — Return `202 Accepted` + job ID immediately; poll `GET /api/jobs/{id}` for status. Eliminates the 30s synchronous wait and proxy timeout risk.

2. **AI "Explain more" button** — After flipping a card, show a button that queries the vector store for related chunks and sends them to Groq for a detailed explanation. This is why ChromaDB is architected in even though disabled in prod.

3. **Export to Anki (.apkg) / CSV** — Study material should be portable. Anki export would make FlashMind a genuinely useful tool, not just a demo.

4. **Heat map calendar** — GitHub-style contribution graph for study consistency. More motivating than a bar chart.

5. **Multi-PDF deck merging** — Upload multiple PDFs into one deck. Useful for exam prep across several chapters.

6. **Achievement badges** — "7-day streak", "100 cards reviewed", "Perfect session". Light gamification that increases retention.

7. **Configurable card count** — Let users choose 5, 10, or 20 cards per PDF.

8. **MongoDB aggregation for stats** — Replace Python-side aggregation with `$group` pipeline queries.

---

## How to Run Locally

```bash
git clone https://github.com/SannidhiSriram-06/flashmind.git
cd flashmind
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env with:
# MONGODB_URI=mongodb+srv://...
# GROQ_API_KEY=gsk_...
# SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

uvicorn app.main:app --reload
# Open http://localhost:8000
```

The `.env` file is gitignored. All secrets must be set before starting the server — there are no insecure fallbacks (auth.py will raise `RuntimeError` if `SECRET_KEY` is missing).
