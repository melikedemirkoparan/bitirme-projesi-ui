# ── Embedding function wrapper ───────────────────────────────────
# This is the single place in the codebase that binds to a specific
# embedding model.  To swap the model, change _DEFAULT_MODEL or pass
# a different model_name when calling get_embedding_function().

from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

_DEFAULT_MODEL = "all-MiniLM-L6-v2"


def get_embedding_function(model_name: str = _DEFAULT_MODEL):
    """
    Return a ChromaDB-compatible embedding function.

    The returned object is passed directly to
    chromadb.Client.get_or_create_collection(embedding_function=...).

    Swap `model_name` (or replace the underlying implementation) here
    without touching any other ingestion module.
    """
    return SentenceTransformerEmbeddingFunction(model_name=model_name)
