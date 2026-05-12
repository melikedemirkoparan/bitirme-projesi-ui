"""Two-stage Chroma retrieval for the definition generator.

Stage A: domain text   ->  patent_description_title_en  ->  top-N distinct titles
Stage B: element_name  ->  patent_definition_en (filtered by titles)
                       ->  top-k hits

The two stages are pure functions over the configured Chroma client.
Each stage is independently usable; `retrieve()` composes them.

Threshold semantics: scores are cosine similarities in [-1, 1] (with
collections built using `hnsw:space=cosine`). A hit is dropped if its
score falls below `SIMILARITY_THRESHOLD`.

If a domain is provided but Stage A returns nothing above threshold,
Stage B falls back to an UNFILTERED search rather than returning empty.
This keeps the pipeline useful when the domain term is novel relative
to the indexed corpus.
"""

from __future__ import annotations

from app.ingestion.chroma_client import get_chroma_client
from app.ingestion.embedding import get_embedding_function

_TITLE_COLLECTION = "patent_description_title_en"
_DEFINITION_COLLECTION = "patent_definition_en"

# e5-base on multilingual queries typically scores 0.75+ on good
# matches and 0.5-0.7 on weak matches. 0.55 keeps relevant titles in
# while filtering near-random ones. Tunable per-deployment if needed.
SIMILARITY_THRESHOLD = 0.55


def is_data_loaded() -> bool:
    """True if the definition collection exists and has at least one doc."""
    return get_definition_count() > 0


def get_definition_count() -> int:
    """Return the current size of the definition collection, or 0 if
    Chroma is unreachable or the collection has not been built yet.

    Used by the data-status endpoint so the UI can show the persisted
    count after a restart, not just the count from the latest upload.
    """
    try:
        client = get_chroma_client()
        existing = {c.name for c in client.list_collections()}
        if _DEFINITION_COLLECTION not in existing:
            return 0
        coll = client.get_collection(_DEFINITION_COLLECTION)
        return int(coll.count() or 0)
    except Exception:
        return 0


def retrieve_titles_by_domain(domain: str, top_k: int = 5) -> list[str]:
    """Stage A — semantic search over the title collection by domain text.

    Returns up to `top_k` DISTINCT description_title_en values whose
    similarity is above SIMILARITY_THRESHOLD. We over-fetch because each
    element row carries the same title, so a single title appears many
    times in the collection — dedup may shrink the set significantly.
    """
    if not domain or not domain.strip():
        return []
    try:
        client = get_chroma_client()
        embedding_fn = get_embedding_function()
        coll = client.get_or_create_collection(
            name=_TITLE_COLLECTION,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        if coll.count() == 0:
            return []

        n_results = min(max(top_k * 5, 50), coll.count())
        result = coll.query(query_texts=[domain.strip()], n_results=n_results)

        documents = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0]

        seen: set[str] = set()
        titles: list[str] = []
        for doc, dist in zip(documents, distances):
            score = 1 - float(dist)
            if score < SIMILARITY_THRESHOLD:
                continue
            t = (doc or "").strip()
            if not t or t in seen:
                continue
            seen.add(t)
            titles.append(t)
            if len(titles) >= top_k:
                break
        return titles
    except Exception as exc:
        print(f"[chroma_retrieval] Stage A failed: {exc}")
        return []


def retrieve_definitions(
    element_name: str,
    title_filter: list[str] | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Stage B — semantic search over the definition collection by
    element_name, optionally filtered by description_title_en.

    Returns hit dicts shaped like the legacy `rag_engine.retrieve` output
    so the definition pipeline can consume them without further changes:
      { score, element_name_en, definition_en, title_en, context_en,
        element_name_tr, definition_tr }
    """
    if not element_name or not element_name.strip():
        return []
    try:
        client = get_chroma_client()
        embedding_fn = get_embedding_function()
        coll = client.get_or_create_collection(
            name=_DEFINITION_COLLECTION,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        if coll.count() == 0:
            return []

        where = None
        if title_filter:
            # Chroma $in filter requires at least one value; empty list is invalid.
            where = {"description_title_en": {"$in": title_filter}}

        # Cap n_results by collection size to avoid Chroma errors on small corpora.
        n_results = min(top_k, coll.count())
        result = coll.query(
            query_texts=[element_name.strip()],
            n_results=n_results,
            where=where,
        )

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        hits: list[dict] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            score = 1 - float(dist)
            if score < SIMILARITY_THRESHOLD:
                continue
            meta = meta or {}
            hits.append({
                "score": round(score, 4),
                "element_name_en": meta.get("element_name_en", ""),
                "definition_en": doc or "",
                "title_en": meta.get("description_title_en", ""),
                "context_en": meta.get("all_elements_context_en", ""),
                "element_name_tr": meta.get("element_name_tr", ""),
                "definition_tr": meta.get("definition_tr", ""),
            })
        return hits
    except Exception as exc:
        print(f"[chroma_retrieval] Stage B failed: {exc}")
        return []


def retrieve(
    element_name: str,
    domain: str | None = None,
    top_k: int = 5,
    top_k_titles: int = 5,
) -> list[dict]:
    """Compose Stage A (if domain provided) then Stage B.

    If `domain` is empty/None, the title filter is skipped and Stage B
    runs against the full corpus — same behavior as the legacy retrieval
    so projects without a domain field still work.

    If domain is provided but Stage A finds nothing above threshold, we
    fall back to an unfiltered Stage B (rather than returning empty)
    because a novel domain term shouldn't kill the suggestion entirely.
    """
    title_filter: list[str] | None = None
    if domain and domain.strip():
        title_filter = retrieve_titles_by_domain(domain, top_k=top_k_titles)
        if not title_filter:
            title_filter = None
    return retrieve_definitions(element_name, title_filter=title_filter, top_k=top_k)
