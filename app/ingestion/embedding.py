# ── Embedding function wrapper ───────────────────────────────────
# This is the single place in the codebase that binds to a specific
# embedding model.  To swap the model, change _DEFAULT_MODEL or pass
# a different model_name when calling get_embedding_function().

from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

_DEFAULT_MODEL = "intfloat/multilingual-e5-base"

# Singleton cache keyed by model name. SentenceTransformerEmbeddingFunction
# loads the underlying model (~470 MB for e5-base) at construction time;
# without this cache every call site allocates a fresh copy of the weights
# plus activations, which on CPU peaks at ~1 GB per instance. Two retrieval
# stages + one ingestion build = 3× duplicated weights — enough to OOM-kill
# the container under modest Docker memory limits.
_INSTANCES: dict[str, SentenceTransformerEmbeddingFunction] = {}


def get_embedding_function(model_name: str = _DEFAULT_MODEL):
    """
    Return a ChromaDB-compatible embedding function. Cached per model name.

    The returned object is passed directly to
    chromadb.Client.get_or_create_collection(embedding_function=...).

    Swap `model_name` (or replace the underlying implementation) here
    without touching any other ingestion module.
    """
    if model_name not in _INSTANCES:
        _INSTANCES[model_name] = SentenceTransformerEmbeddingFunction(
            model_name=model_name
        )
    return _INSTANCES[model_name]
