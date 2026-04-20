import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

_client: MongoClient | None = None


def _get_client() -> MongoClient:
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI is not set in the environment")
        _client = MongoClient(uri)
    return _client


def get_db():
    """Return the flashmind database. Collections: users, decks, study_sessions."""
    return _get_client()["flashmind"]
