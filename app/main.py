import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from app.api.auth_routes import router as auth_router
from app.api.decks import router as decks_router
from app.api.history_routes import router as history_router
from app.db import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    db = get_db()
    db.users.create_index("email", unique=True)
    db.decks.create_index("user_id")
    db.study_sessions.create_index([("user_id", 1), ("date", 1)])
    print("\n🚀  FlashMind running at http://localhost:8000")
    print(f"    ENV={os.environ.get('ENV','development')}  "
          f"VECTOR_STORE={'disabled' if os.environ.get('DISABLE_VECTOR_STORE','').lower()=='true' else 'enabled'}\n")
    yield
    # ── Shutdown (nothing to clean up) ───────────────────────────────────────


app = FastAPI(title="FlashMind", lifespan=lifespan)

# CORS: read from env so production origins work on Render
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:8000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,    prefix="/api/auth")
app.include_router(decks_router,   prefix="/api")
app.include_router(history_router, prefix="/api")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return FileResponse("static/index.html")
