import os
import random
import uuid
from datetime import datetime

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth import (
    create_session_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db import get_db

router = APIRouter()

_AVATAR_COLORS = [
    "#4f8ef7",  # blue
    "#22c55e",  # green
    "#f97316",  # orange
    "#a855f7",  # purple
    "#ec4899",  # pink
    "#14b8a6",  # teal
    "#f59e0b",  # amber
    "#ef4444",  # red
]

_COOKIE_OPTS = dict(
    httponly=True,
    max_age=604800,
    samesite="lax",
    secure=os.environ.get("ENV") == "production",
)


def _set_session(response: Response, user_id: str) -> str:
    token = create_session_token(user_id)
    response.set_cookie("session", token, **_COOKIE_OPTS)
    return token


def _safe_user(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in ("_id", "password_hash")}


# ── Signup ────────────────────────────────────────────────────────────────────

class SignupBody(BaseModel):
    email: str
    password: str
    display_name: str


@router.post("/signup")
def signup(body: SignupBody, response: Response):
    # Validate email
    try:
        validated = validate_email(body.email, check_deliverability=False)
        email = validated.email
    except EmailNotValidError as e:
        raise HTTPException(status_code=400, detail=f"Invalid email: {e}")

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if not body.display_name.strip():
        raise HTTPException(status_code=400, detail="Display name cannot be empty")

    db = get_db()
    if db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user_id = str(uuid.uuid4())
    user_doc = {
        "user_id": user_id,
        "email": email,
        "password_hash": hash_password(body.password),
        "display_name": body.display_name.strip(),
        "created_at": datetime.utcnow().isoformat(),
        "avatar_color": random.choice(_AVATAR_COLORS),
    }
    db.users.insert_one(user_doc)
    _set_session(response, user_id)
    return _safe_user(user_doc)


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(body: LoginBody, response: Response):
    try:
        validated = validate_email(body.email, check_deliverability=False)
        email = validated.email
    except EmailNotValidError:
        raise HTTPException(status_code=400, detail="Invalid email format")

    db = get_db()
    user = db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    _set_session(response, user["user_id"])
    return _safe_user(user)


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me")
def me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ── Update display name ───────────────────────────────────────────────────────

class ProfileBody(BaseModel):
    display_name: str


@router.put("/profile")
def update_profile(body: ProfileBody, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not body.display_name.strip():
        raise HTTPException(status_code=400, detail="Display name cannot be empty")

    db = get_db()
    db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"display_name": body.display_name.strip()}},
    )
    user["display_name"] = body.display_name.strip()
    return user


# ── Change password ───────────────────────────────────────────────────────────

class PasswordBody(BaseModel):
    current_password: str
    new_password: str


@router.put("/password")
def change_password(body: PasswordBody, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db = get_db()
    full_user = db.users.find_one({"user_id": user["user_id"]})
    if not verify_password(body.current_password, full_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"password_hash": hash_password(body.new_password)}},
    )
    return {"ok": True}


# ── Delete account ────────────────────────────────────────────────────────────

class DeleteAccountBody(BaseModel):
    password: str


@router.delete("/account")
def delete_account(body: DeleteAccountBody, request: Request, response: Response):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db = get_db()
    full_user = db.users.find_one({"user_id": user["user_id"]})
    if not verify_password(body.password, full_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect password")

    # Clean up ChromaDB collections for each deck
    from app.core.vector_store import delete_collection
    for deck in db.decks.find({"user_id": user["user_id"]}, {"deck_id": 1}):
        delete_collection(deck["deck_id"])

    db.decks.delete_many({"user_id": user["user_id"]})
    db.study_sessions.delete_many({"user_id": user["user_id"]})
    db.users.delete_one({"user_id": user["user_id"]})

    response.delete_cookie("session")
    return {"ok": True}
