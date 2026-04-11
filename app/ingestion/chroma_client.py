# ── ChromaDB persistent client ───────────────────────────────────
# Exposes a single function that returns a module-level singleton
# persistent client.  Storage path comes from app settings so it
# can be overridden via the .env file.

import chromadb

from app.config import settings

_client: chromadb.PersistentClient | None = None


def get_chroma_client() -> chromadb.PersistentClient:
    """
    Return the application-level persistent ChromaDB client.

    The client is created once and reused for all subsequent calls
    within the same process.  Storage is written to
    settings.chroma_storage_path (default: ./storage).
    """
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_storage_path)
    return _client
