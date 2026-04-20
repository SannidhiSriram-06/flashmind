from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request

from app.auth import get_current_user
from app.db import get_db

router = APIRouter()


def _require_user(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _is_easy(s: dict) -> bool:
    """quality==5 (Easy), or legacy result=='know'."""
    if "quality" in s:
        return s["quality"] == 5
    return s.get("result") == "know"


def _is_hard(s: dict) -> bool:
    """quality==2 (Hard); no equivalent in legacy schema."""
    return s.get("quality") == 2


def _is_again(s: dict) -> bool:
    """quality==0 (Again), or legacy result=='dont_know'."""
    if "quality" in s:
        return s["quality"] == 0
    return s.get("result") == "dont_know"


# ── GET /api/history ──────────────────────────────────────────────────────────

@router.get("/history")
def get_history(request: Request):
    user = _require_user(request)
    db = get_db()

    # Build a date window: last 30 days
    today = date.today()
    date_window = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]

    sessions = list(db.study_sessions.find(
        {"user_id": user["user_id"], "date": {"$in": date_window}},
        {"_id": 0, "date": 1, "quality": 1, "result": 1},
    ))

    by_date: dict[str, dict] = {
        d: {"date": d, "total": 0, "easy": 0, "hard": 0, "again": 0}
        for d in date_window
    }
    for s in sessions:
        d = s["date"]
        if d in by_date:
            by_date[d]["total"] += 1
            if _is_easy(s):
                by_date[d]["easy"] += 1
            elif _is_hard(s):
                by_date[d]["hard"] += 1
            else:
                by_date[d]["again"] += 1

    result = []
    for d in date_window:
        entry = by_date[d]
        dt = date.fromisoformat(d)
        result.append({
            "date": f"{dt.strftime('%b')} {dt.day}",
            "total": entry["total"],
            "easy": entry["easy"],
            "hard": entry["hard"],
            "again": entry["again"],
            # backward-compat aliases used by existing frontend code
            "known": entry["easy"],
            "learning": entry["again"],
        })
    return result


# ── GET /api/stats ────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(request: Request):
    user = _require_user(request)
    db = get_db()
    user_id = user["user_id"]

    total_decks = db.decks.count_documents({"user_id": user_id})

    sessions = list(db.study_sessions.find(
        {"user_id": user_id},
        {"_id": 0, "quality": 1, "result": 1, "date": 1},
    ))

    total_sessions = len(sessions)
    easy_count = sum(1 for s in sessions if _is_easy(s))
    average_score = round((easy_count / total_sessions) * 100) if total_sessions else 0

    # Best streak: longest run of consecutive days with ≥1 session
    active_dates = sorted({s["date"] for s in sessions})
    best_streak = 0
    current_streak = 0
    prev: date | None = None
    for d_str in active_dates:
        d = date.fromisoformat(d_str)
        if prev is not None and (d - prev).days == 1:
            current_streak += 1
        else:
            current_streak = 1
        best_streak = max(best_streak, current_streak)
        prev = d

    return {
        "total_decks": total_decks,
        "total_cards_studied": total_sessions,
        "total_sessions": total_sessions,
        "average_score": average_score,
        "best_streak": best_streak,
    }
