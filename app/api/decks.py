import shutil
import time
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

from app.auth import get_current_user
from app.core.pdf_parser import extract_text_chunks
from app.core.vector_store import store_chunks, delete_collection
from app.core.flashcard_gen import generate_flashcards
from app.db import get_db

router = APIRouter()

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

# ── Rate limiter (in-memory, 5 uploads / IP / hour) ──────────────────────────
_upload_log: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 5
RATE_WINDOW = 3600


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    _upload_log[ip] = [t for t in _upload_log[ip] if now - t < RATE_WINDOW]
    if len(_upload_log[ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Upload limit reached: max {RATE_LIMIT} uploads per hour.",
        )
    _upload_log[ip].append(now)


# ── Auth dependency ───────────────────────────────────────────────────────────

def _require_user(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


# ── MongoDB helpers ───────────────────────────────────────────────────────────

def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


def _load_deck(deck_id: str, user_id: str) -> dict:
    db = get_db()
    deck = db.decks.find_one({"deck_id": deck_id})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    if deck["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return _clean(deck)


def _due_count(deck: dict) -> int:
    today = date.today().isoformat()
    card_states = deck.get("card_states", {})
    count = 0
    for i in range(len(deck["cards"])):
        state = card_states.get(str(i))
        if state is None or state.get("next_review", today) <= today:
            count += 1
    return count


# ── POST /api/upload ──────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    user = _require_user(request)
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    deck_id = str(uuid.uuid4())
    deck_name = Path(file.filename).stem
    pdf_path = UPLOADS_DIR / f"{deck_id}.pdf"

    with pdf_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    if pdf_path.stat().st_size > MAX_FILE_BYTES:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB size limit")

    try:
        chunks = extract_text_chunks(str(pdf_path))
    except ValueError as e:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"PDF processing error: {e}")
    finally:
        pdf_path.unlink(missing_ok=True)

    try:
        store_chunks(deck_id, chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector store error: {e}")

    try:
        chunk_texts = [c["text"] for c in chunks]
        cards = generate_flashcards(chunk_texts, topic_hint=deck_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flashcard generation error: {e}")

    deck = {
        "deck_id": deck_id,
        "user_id": user["user_id"],
        "name": deck_name,
        "created_at": datetime.utcnow().isoformat(),
        "cards": cards,
        "card_states": {},
    }
    get_db().decks.insert_one(deck)

    return {"deck_id": deck_id, "name": deck_name, "card_count": len(cards)}


# ── GET /api/decks ────────────────────────────────────────────────────────────

@router.get("/decks")
def list_decks(request: Request):
    user = _require_user(request)
    db = get_db()
    decks = []
    for doc in db.decks.find({"user_id": user["user_id"]}, sort=[("created_at", 1)]):
        _clean(doc)
        decks.append({
            "deck_id": doc["deck_id"],
            "name": doc["name"],
            "card_count": len(doc["cards"]),
            "created_at": doc["created_at"],
            "due_count": _due_count(doc),
        })
    return decks


# ── GET /api/decks/{deck_id} ──────────────────────────────────────────────────

@router.get("/decks/{deck_id}")
def get_deck(deck_id: str, request: Request):
    user = _require_user(request)
    return _load_deck(deck_id, user["user_id"])


# ── DELETE /api/decks/{deck_id} ───────────────────────────────────────────────

@router.delete("/decks/{deck_id}")
def delete_deck(deck_id: str, request: Request):
    user = _require_user(request)
    _load_deck(deck_id, user["user_id"])  # 404 / 403 guard

    get_db().decks.delete_one({"deck_id": deck_id, "user_id": user["user_id"]})
    get_db().study_sessions.delete_many({"deck_id": deck_id, "user_id": user["user_id"]})
    delete_collection(deck_id)
    return {"deleted": deck_id}


# ── POST /api/decks/{deck_id}/review ─────────────────────────────────────────

class ReviewBody(BaseModel):
    card_index: int
    quality: int  # 0 = Again, 2 = Hard, 5 = Easy


@router.post("/decks/{deck_id}/review")
def review_card(deck_id: str, body: ReviewBody, request: Request):
    user = _require_user(request)
    deck = _load_deck(deck_id, user["user_id"])
    db = get_db()

    if body.card_index < 0 or body.card_index >= len(deck["cards"]):
        raise HTTPException(status_code=400, detail="card_index out of range")
    if body.quality not in (0, 2, 5):
        raise HTTPException(status_code=400, detail="quality must be 0 (Again), 2 (Hard), or 5 (Easy)")

    key = str(body.card_index)
    state = deck["card_states"].get(key, {
        "interval": 1,
        "ease": 2.5,
        "repetitions": 0,
        "next_review": date.today().isoformat(),
    })

    if body.quality == 0:  # Again — complete blank, reset
        state["repetitions"] = 0
        state["interval"] = 1
        state["ease"] = max(1.3, round(state["ease"] - 0.2, 2))
        next_date = date.today() + timedelta(days=1)
    elif body.quality == 2:  # Hard — got it but struggled
        state["repetitions"] += 1
        state["interval"] = max(1, round(state["interval"] * 0.8, 2))
        state["ease"] = max(1.3, round(state["ease"] - 0.15, 2))
        next_date = date.today() + timedelta(days=max(1, int(state["interval"])))
    else:  # quality == 5, Easy — knew it cold
        state["repetitions"] += 1
        state["interval"] = round(state["interval"] * state["ease"], 2)
        state["ease"] = min(3.0, round(state["ease"] + 0.1, 2))
        next_date = date.today() + timedelta(days=max(1, int(state["interval"])))

    state["next_review"] = next_date.isoformat()

    db.decks.update_one(
        {"deck_id": deck_id, "user_id": user["user_id"]},
        {"$set": {f"card_states.{key}": state}},
    )

    db.study_sessions.insert_one({
        "user_id": user["user_id"],
        "deck_id": deck_id,
        "deck_name": deck["name"],
        "card_index": body.card_index,
        "quality": body.quality,
        "timestamp": datetime.utcnow().isoformat(),
        "date": date.today().isoformat(),
    })

    return state
