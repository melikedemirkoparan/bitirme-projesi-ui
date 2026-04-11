# ── Collection builder ────────────────────────────────────────────
# Responsible for building a single ChromaDB collection from a list
# of parsed rows.
#
# Contract: the collection is assumed to be empty (freshly created or
# just reset by the orchestrator).  Use `add` not `upsert` — there is
# no prior state to merge with.
#
# Document IDs are UUID-based: opaque, always unique, no dependency on
# any data field.  Stable cross-ingestion IDs are not needed because
# the intended behavior is a full clean rebuild on every upload.

from __future__ import annotations

import uuid

import chromadb

# ChromaDB recommends keeping batch sizes below ~5 000; we use 500
# to stay safely within memory limits for large files.
_BATCH_SIZE = 500


def _safe_metadata_value(val) -> str | None:
    """
    Return a metadata-safe string, or None if the value is unusable.

    Design note: ChromaDB supports str | int | float | bool metadata
    values.  We normalise everything to str here as an intentional
    simplification — it keeps downstream query code uniform and avoids
    type inference surprises from mixed Excel columns.  If typed
    metadata becomes important (e.g. numeric range filters), this
    function is the single place to change.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    return s


def build_collection(
    client: chromadb.PersistentClient,
    embedding_fn,
    collection_name: str,
    target_key: str,
    rows: list[dict],
    metadata_keys: list[str],
) -> int:
    """
    Build a ChromaDB collection from parsed rows.

    Assumes the collection is empty — the caller (ingest_service) is
    responsible for deleting any prior collection before calling this.

    Only rows where the target_key value is a non-empty, non-'nan'
    string are inserted.  Each document receives a UUID as its ID.

    Returns the number of documents added.
    """
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
    )

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    for row in rows:
        text = row.get(target_key)
        if not text:
            continue
        text = str(text).strip()
        if not text or text.lower() == "nan":
            continue

        # Build metadata dict — only keys with usable string values are included
        meta: dict[str, str] = {}
        for key in metadata_keys:
            safe_val = _safe_metadata_value(row.get(key))
            if safe_val is not None:
                meta[key] = safe_val

        documents.append(text)
        metadatas.append(meta)
        ids.append(str(uuid.uuid4()))

    if not documents:
        return 0

    # Batch add to avoid memory spikes on large files
    for batch_start in range(0, len(documents), _BATCH_SIZE):
        batch_end = batch_start + _BATCH_SIZE
        collection.add(
            documents=documents[batch_start:batch_end],
            metadatas=metadatas[batch_start:batch_end],
            ids=ids[batch_start:batch_end],
        )

    return len(documents)
