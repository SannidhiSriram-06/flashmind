# FlashMind — Technical Architecture

---

## System Overview

FlashMind is a single-server web application built on FastAPI. The browser communicates exclusively with the FastAPI backend over HTTP; there is no separate frontend server or build pipeline. All HTML, CSS, and JavaScript is served as a single static file (`static/index.html`). The backend handles authentication, PDF processing, LLM calls, spaced-repetition state, and serving the SPA.

In production, ChromaDB and its embedding model are fully disabled via an environment flag, reducing the deployment image to a lightweight footprint with no ML dependencies.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Browser (SPA)                          │
│              static/index.html  ·  Vanilla JS/CSS               │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / Cookie session
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Railway / Render  —  FastAPI + Uvicorn             │
│                                                                 │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  auth_routes.py │  │   decks.py   │  │ history_routes.py │  │
│  │  /api/auth/*    │  │ /api/upload  │  │  /api/history     │  │
│  │  signup/login   │  │ /api/decks/* │  │  /api/stats       │  │
│  │  logout/profile │  │ /review      │  │                   │  │
│  └─────────────────┘  └──────┬───────┘  └───────────────────┘  │
│                              │                                  │
│          ┌───────────────────┼─────────────────┐               │
│          ▼                   ▼                 ▼               │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  pdf_parser   │  │ flashcard_   │  │   vector_store.py    │ │
│  │  .py          │  │ gen.py       │  │   ChromaDB           │ │
│  │  pdfplumber   │  │ Groq API     │  │   (disabled in prod) │ │
│  └───────────────┘  └──────────────┘  └──────────────────────┘ │
└──────────────┬───────────────────────────────────────────────────┘
               │
       ┌───────┴──────────────────┐
       │                          │
       ▼                          ▼
┌─────────────────┐     ┌──────────────────┐
│  MongoDB Atlas  │     │    Groq API       │
│                 │     │  llama-3.1-8b-    │
│  users          │     │  instant          │
│  decks          │     └──────────────────┘
│  study_sessions │
└─────────────────┘
```

---

## Component Breakdown

| Component | File | Responsibility |
|---|---|---|
| **App entrypoint** | `app/main.py` | FastAPI app, lifespan, MongoDB indexes, security headers middleware, CORS, static file serving |
| **Auth** | `app/auth.py` | bcrypt password hashing/verification, itsdangerous session token creation/verification |
| **Auth routes** | `app/api/auth_routes.py` | Signup, login (with rate limiting), logout, `/me`, profile update, password change, account deletion |
| **Deck routes** | `app/api/decks.py` | PDF upload (with per-IP rate limiting), deck CRUD, SM-2 review endpoint |
| **History routes** | `app/api/history_routes.py` | 30-day review history, aggregate stats (streak, average score, session count) |
| **PDF parser** | `app/core/pdf_parser.py` | pdfplumber text extraction with 500-char / 50-char overlap chunking |
| **Flashcard gen** | `app/core/flashcard_gen.py` | 3-attempt Groq LLM call with escalating system prompts, JSON validation |
| **Vector store** | `app/core/vector_store.py` | ChromaDB + `all-MiniLM-L6-v2` semantic search (no-op when `DISABLE_VECTOR_STORE=true`) |
| **Database** | `app/db.py` | Singleton pymongo client, `flashmind` database |
| **SPA** | `static/index.html` | Full UI: auth screens, deck management, study mode, stats, history — all CSS and JS inline |

---

## Request Flow: PDF Upload

```
1. Browser           POST /api/upload  (multipart/form-data, PDF file)

2. decks.py          Authenticate user via session cookie
                     Check per-IP rate limit (5 uploads / hour)
                     Validate .pdf extension

3. decks.py          Save PDF to uploads/ directory temporarily
                     Check file size ≤ 10 MB

4. pdf_parser.py     Open PDF with pdfplumber
                     For each page: extract text, split into 500-char chunks
                       with 50-char overlap between chunks
                     Raise ValueError if PDF is encrypted or has no text

5. vector_store.py   If DISABLE_VECTOR_STORE=false:
                       Encode chunks with all-MiniLM-L6-v2
                       Store embeddings in ChromaDB collection named by deck_id
                     If DISABLE_VECTOR_STORE=true: no-op

6. flashcard_gen.py  Concatenate chunk texts, truncate to 4000 chars
                     Prepend "Topic: <filename>" hint
                     Attempt 1: call Groq with standard system prompt
                     Attempt 2 (if JSON invalid): stricter system prompt
                     Attempt 3 (if still invalid): fallback bare-JSON prompt
                     Parse and validate [{front, back}, ...] structure

7. decks.py          Insert deck document into MongoDB:
                       deck_id, user_id, name, created_at, cards[], card_states={}
                     Delete temporary PDF file

8. Browser           Receive {deck_id, name, card_count}
                     Show success toast; reload deck list
```

---

## Request Flow: Study Session Review

```
1. Browser           User clicks Again / Hard / Easy button
                     POST /api/decks/{deck_id}/review
                     Body: {card_index: <original index>, quality: 0|2|5}

2. decks.py          Authenticate user
                     Load deck, verify ownership
                     Validate card_index and quality values

3. decks.py          Load card state from deck.card_states[str(card_index)]
                     Default state if unseen: {interval:1, ease:2.5, repetitions:0}
                     Apply SM-2 formula (see below)
                     Compute next_review date

4. MongoDB           Update deck.card_states[str(card_index)] atomically
                     Insert study_sessions document:
                       user_id, deck_id, deck_name, card_index,
                       quality, timestamp, date

5. Browser           Receive updated card state
                     If quality==0: re-insert card 3–7 positions ahead in queue
                     Advance to next card with 120ms exit animation
```

---

## SM-2 Algorithm

FlashMind implements a modified SM-2 scheduling algorithm with three quality levels instead of the original 0–5 scale.

### Quality levels

| Button | Quality | Meaning |
|---|---|---|
| Again | 0 | Complete blank — could not recall |
| Hard | 2 | Recalled with significant effort |
| Easy | 5 | Recalled instantly and correctly |

### State per card

```python
{
    "interval":    float,   # Days until next review
    "ease":        float,   # Ease factor (1.3–3.0, default 2.5)
    "repetitions": int,     # Successful review count
    "next_review": str,     # ISO date string YYYY-MM-DD
}
```

### Update formulas

**Again (quality = 0) — reset:**
```
repetitions = 0
interval    = 1
ease        = max(1.3, ease - 0.2)
next_review = today + 1 day
```

**Hard (quality = 2) — short progress:**
```
repetitions += 1
interval    = max(1, round(interval * ease * 0.8, 2))
ease        = max(1.3, ease - 0.15)
next_review = today + max(1, int(interval)) days
```

**Easy (quality = 5) — full progress:**
```
repetitions += 1
interval    = max(1, round(interval * ease, 2))
ease        = min(3.0, ease + 0.1)
next_review = today + max(1, int(interval)) days
```

### In-session re-queue

Cards rated "Again" are not removed from the session. Instead, a copy is spliced back into `S.queue` at a random offset of 3–7 positions ahead of the current position. This guarantees the card reappears before the session ends, regardless of deck size.

---

## Security Architecture

### Authentication

- Passwords hashed with **bcrypt** (auto-salted, work factor default ~12).
- Sessions stored in an **HttpOnly, SameSite=Strict** cookie (`session`).
- Cookie value is a signed timestamp token produced by `itsdangerous.TimestampSigner` with a 7-day max age.
- On every authenticated request, the token is verified and the user document is fetched from MongoDB.

### Rate Limiting

- **Login:** 10 attempts per IP per 15-minute sliding window. Exceeding returns HTTP 429.
- **Upload:** 5 uploads per IP per hour. Exceeding returns HTTP 429.
- Both limiters use in-memory `defaultdict(list)` with time-based sliding windows (no Redis dependency).

### Security Headers (applied to every response)

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `X-XSS-Protection` | `1; mode=block` |

### Input Validation

- Email addresses validated with `email-validator` (RFC-compliant, no DNS check).
- Passwords require minimum 8 characters.
- File uploads checked for `.pdf` extension and 10 MB size limit before processing.
- `card_index` and `quality` validated against allowlist before any database write.

---

## Data Models

### User document (`users` collection)

```json
{
  "user_id":      "uuid4-string",
  "email":        "user@example.com",
  "password_hash": "$2b$12$...",
  "display_name": "Jane",
  "created_at":   "2026-01-15T10:30:00",
  "avatar_color": "#4f8ef7"
}
```

### Deck document (`decks` collection)

```json
{
  "deck_id":    "uuid4-string",
  "user_id":   "uuid4-string",
  "name":      "Calculus Notes",
  "created_at": "2026-01-15T10:31:00",
  "cards": [
    { "front": "What is a derivative?", "back": "The rate of change of a function." },
    { "front": "...", "back": "..." }
  ],
  "card_states": {
    "0": {
      "interval":    4.5,
      "ease":        2.6,
      "repetitions": 3,
      "next_review": "2026-01-20"
    },
    "1": { "interval": 1, "ease": 2.3, "repetitions": 0, "next_review": "2026-01-16" }
  }
}
```

### StudySession document (`study_sessions` collection)

```json
{
  "user_id":   "uuid4-string",
  "deck_id":   "uuid4-string",
  "deck_name": "Calculus Notes",
  "card_index": 0,
  "quality":    5,
  "timestamp": "2026-01-15T11:00:00",
  "date":      "2026-01-15"
}
```

### MongoDB Indexes

```python
db.users.create_index("email", unique=True)
db.decks.create_index("user_id")
db.study_sessions.create_index([("user_id", 1), ("date", 1)])
```
