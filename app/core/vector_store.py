import os

# Set DISABLE_VECTOR_STORE=true to skip all ChromaDB/embedding operations
# (useful on Render free tier where memory is constrained or filesystem is ephemeral)
_DISABLED = os.environ.get("DISABLE_VECTOR_STORE", "").lower() == "true"

_chroma_client = None
_embed_model = None


def _get_client():
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path="chroma_db")
    return _chroma_client


def _get_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def init_collection(deck_id: str):
    """Create or retrieve a ChromaDB collection for the given deck."""
    if _DISABLED:
        return None
    return _get_client().get_or_create_collection(name=deck_id)


def store_chunks(deck_id: str, chunks: list[dict]) -> None:
    """Embed each chunk and store in the collection. No-op if vector store is disabled."""
    if _DISABLED:
        return
    collection = init_collection(deck_id)
    texts = [c["text"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    metadatas = [{"page": c["page"]} for c in chunks]
    model = _get_model()

    # Insert in batches of 100 to avoid ChromaDB limits on large PDFs
    batch_size = 100
    for start in range(0, len(texts), batch_size):
        batch_texts = texts[start:start + batch_size]
        batch_ids   = ids[start:start + batch_size]
        batch_meta  = metadatas[start:start + batch_size]
        embeddings  = model.encode(batch_texts).tolist()
        collection.add(documents=batch_texts, embeddings=embeddings,
                       ids=batch_ids, metadatas=batch_meta)


def query_chunks(deck_id: str, query_text: str, n: int = 5) -> list[str]:
    """Return the top-n most relevant chunk texts. Returns [] if disabled."""
    if _DISABLED:
        return []
    collection = init_collection(deck_id)
    model = _get_model()
    query_embedding = model.encode([query_text]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=n)
    return results["documents"][0] if results["documents"] else []


def delete_collection(deck_id: str) -> None:
    """Delete the ChromaDB collection for the given deck. No-op if disabled."""
    if _DISABLED:
        return
    try:
        _get_client().delete_collection(name=deck_id)
    except Exception:
        pass
