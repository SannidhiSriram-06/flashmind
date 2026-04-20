# FlashMind

**Turn any PDF into a smart flashcard deck — in seconds.**

![Python](https://img.shields.io/badge/Python-3.11-3776ab?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47a248?style=flat-square&logo=mongodb&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLaMA%203.1-f55036?style=flat-square)
![Railway](https://img.shields.io/badge/Deploy-Railway-0b0d0e?style=flat-square&logo=railway&logoColor=white)
![License](https://img.shields.io/badge/License-MIT%20%2B%20Commons%20Clause-blue?style=flat-square)

---

## Screenshots

<!-- Add screenshots here -->

---

## Features

- **AI Flashcard Generation** — Upload any PDF and Groq's LLaMA 3.1 generates 10 targeted flashcards automatically
- **SM-2 Spaced Repetition** — Proven algorithm schedules each card at the optimal review interval
- **3-Button Review** — Rate every card as Again / Hard / Easy for fine-grained SM-2 updates
- **Study History & Stats** — 30-day bar chart, streaks, easy/hard/again breakdowns per session
- **Dark & Light Theme** — macOS-style glass UI that follows your system preference
- **Mobile Responsive** — Full study flow works on phones, including swipe-friendly card flip
- **PDF Upload** — Drag-and-drop or click-to-browse; 10 MB limit, text-based PDFs only
- **Secure Auth** — bcrypt passwords, signed session cookies, rate-limited login, security headers

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Frontend** | Vanilla JS/CSS (single-file SPA, no build step) |
| **AI / LLM** | Groq API — `llama-3.1-8b-instant` |
| **Database** | MongoDB Atlas (pymongo) |
| **Auth** | bcrypt + itsdangerous `TimestampSigner` (7-day sessions) |
| **PDF Parsing** | pdfplumber with 500-char overlapping chunks |
| **Vector Store** | ChromaDB + `all-MiniLM-L6-v2` (disabled in production) |
| **Deployment** | Railway (nixpacks) / Render |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/SannidhiSriram-06/flashmind.git
cd flashmind

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env           # then edit .env with your values
# Minimum required:
#   MONGODB_URI=mongodb+srv://...
#   GROQ_API_KEY=gsk_...
#   SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# 5. Run
uvicorn app.main:app --reload

# Open http://localhost:8000
```

---

## Environment Variables

| Variable | Required | Description | Example |
|---|---|---|---|
| `MONGODB_URI` | **Yes** | MongoDB connection string | `mongodb+srv://user:pass@cluster.mongodb.net/` |
| `GROQ_API_KEY` | **Yes** | Groq API key for LLaMA 3.1 | `gsk_abc123...` |
| `SECRET_KEY` | **Yes** | 32-byte hex secret for session signing | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ENV` | No | Set to `production` to enable secure cookies | `production` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins | `https://flashmind.up.railway.app` |
| `DISABLE_VECTOR_STORE` | No | Skip ChromaDB/embeddings (recommended in production) | `true` |

---

## How It Works

```
PDF Upload
    │
    ▼
pdfplumber          — extract text, split into 500-char overlapping chunks
    │
    ▼
Groq LLaMA 3.1      — generate 10 flashcards as JSON [{front, back}, ...]
    │
    ▼
MongoDB Atlas       — persist deck + per-card SM-2 state (interval, ease, next_review)
    │
    ▼
SM-2 Review Loop
    ├── Again (quality=0)  → reset interval, lower ease, review tomorrow
    ├── Hard  (quality=2)  → short interval × ease × 0.8, ease decreases
    └── Easy  (quality=5)  → interval × ease, ease increases, long gap
```

Each "Again" card is re-inserted 3–7 positions ahead in the current session queue so it comes back before the session ends.

---

## Project Structure

```
flashmind/
├── app/
│   ├── main.py               # FastAPI app, middleware, routes
│   ├── auth.py               # Session tokens, password hashing
│   ├── db.py                 # MongoDB connection
│   ├── api/
│   │   ├── auth_routes.py    # /api/auth/* (signup, login, logout, profile)
│   │   ├── decks.py          # /api/upload, /api/decks/*, /api/decks/{id}/review
│   │   └── history_routes.py # /api/history, /api/stats
│   └── core/
│       ├── pdf_parser.py     # pdfplumber chunking
│       ├── flashcard_gen.py  # Groq LLM calls with 3-attempt retry
│       └── vector_store.py   # ChromaDB (disabled in prod)
├── static/
│   └── index.html            # Single-file SPA (all CSS + JS inline)
├── requirements.txt          # Development dependencies
├── requirements-prod.txt     # Production dependencies (no ChromaDB/torch)
├── nixpacks.toml             # Railway build config
└── render.yaml               # Render deployment config
```

---

## License

MIT License with Commons Clause — see [LICENSE](LICENSE) for details.

Free for personal and educational use. Commercial use requires a separate license.
Contact: sannidhisriram06@zohomail.in
