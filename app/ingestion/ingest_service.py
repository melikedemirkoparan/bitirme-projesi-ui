# ── Ingestion service (orchestrator) ─────────────────────────────
# Ties the parser, ChromaDB client, embedding function, and
# collection builder together.  The route layer calls run_ingestion()
# and receives an IngestResult it can serialise to the frontend.
#
# Ingestion model: clean rebuild on every upload.
#   1. Parse and validate the Excel file.
#   2. Enforce mandatory column presence (definition_en).
#   3. Delete all target collections that exist (reset).
#   4. Rebuild each collection from scratch.
#
# Only one current collection set exists in the system at a time.
# There is no incremental update or upsert behavior.

from __future__ import annotations

from dataclasses import dataclass, field

from app.ingestion.chroma_client import get_chroma_client
from app.ingestion.collection_builder import build_collection
from app.ingestion.embedding import get_embedding_function
from app.ingestion.excel_parser import parse_excel

# ── Collection configuration ─────────────────────────────────────
# Each entry declares:
#   target       — canonical column key that supplies the document text
#   collection   — ChromaDB collection name
#   required     — if True, ingestion fails early when the column is absent
#   metadata_keys— canonical column keys to store as document metadata

COLLECTION_CONFIGS: list[dict] = [
    {
        "target": "definition_en",
        "collection": "patent_definition_en",
        "required": True,
        "metadata_keys": [
            "element_id",
            "element_name_en",
            "element_name_tr",
            "definition_tr",
            "description_title_en",
            "description_title_tr",
            "source_file",
            "location_ref",
            "all_elements_context_en",  # required for context-based filtering in retrieval
        ],
    },
    {
        "target": "description_title_en",
        "collection": "patent_description_title_en",
        "required": False,
        "metadata_keys": [
            "element_id",
            "element_name_en",
            "element_name_tr",
            "description_title_tr",
            "source_file",
        ],
    },
    {
        "target": "all_elements_context_en",
        "collection": "patent_all_elements_context_en",
        "required": False,
        "metadata_keys": [
            "element_id",
            "element_name_en",
            "element_name_tr",
            "description_title_en",
            "description_title_tr",
            "source_file",
        ],
    },
]

# All known collection names — used for the reset step.
_ALL_COLLECTION_NAMES = [cfg["collection"] for cfg in COLLECTION_CONFIGS]


# ── Result types ─────────────────────────────────────────────────

@dataclass
class CollectionResult:
    collection_name: str
    status: str          # "created" | "skipped" | "error"
    doc_count: int = 0
    reason: str = ""


@dataclass
class IngestResult:
    filename: str
    collections: list[CollectionResult] = field(default_factory=list)
    error: str = ""

    @property
    def success(self) -> bool:
        """True if at least one collection was created without error."""
        return not self.error and any(
            r.status == "created" for r in self.collections
        )


# ── Helpers ───────────────────────────────────────────────────────

def _reset_collections(client) -> None:
    """
    Delete all target collections so the next build starts clean.

    Silently ignores collections that do not yet exist.
    Raises if deletion fails for any other reason.
    """
    existing = {c.name for c in client.list_collections()}
    for name in _ALL_COLLECTION_NAMES:
        if name in existing:
            client.delete_collection(name)


# ── Main entry point ─────────────────────────────────────────────

def run_ingestion(file_bytes: bytes, filename: str) -> IngestResult:
    """
    Parse the Excel file and rebuild ChromaDB collections from scratch.

    Mandatory columns:
      - definition_en: ingestion fails early if this column is absent.

    Optional columns (skipped without error if absent):
      - description_title_en
      - all_elements_context_en

    The reset step runs after the file is validated — so a bad upload
    never wipes existing collections.  Per-collection build errors are
    recorded on that collection's result and do not abort the remaining
    collections.
    """
    result = IngestResult(filename=filename)

    # ── 1. Parse ────────────────────────────────────────────────
    try:
        rows, found_targets = parse_excel(file_bytes)
    except ValueError as exc:
        result.error = str(exc)
        return result
    except Exception as exc:
        result.error = f"Unexpected error reading file: {exc}"
        return result

    # ── 2. Enforce mandatory column ──────────────────────────────
    if "definition_en" not in found_targets:
        result.error = (
            "Upload failed: required column 'definition_en' is missing. "
            "Please ensure the Excel file contains a 'Definition (EN)' column."
        )
        return result

    # ── 3. Initialise vector store ───────────────────────────────
    try:
        client = get_chroma_client()
        embedding_fn = get_embedding_function()
    except Exception as exc:
        result.error = f"Failed to initialise vector store: {exc}"
        return result

    # ── 4. Reset existing collections ────────────────────────────
    # Only reached after the file is validated — a bad upload will
    # never wipe existing data.
    try:
        _reset_collections(client)
    except Exception as exc:
        result.error = f"Failed to reset existing collections: {exc}"
        return result

    # ── 5. Build each collection ─────────────────────────────────
    for cfg in COLLECTION_CONFIGS:
        target = cfg["target"]
        coll_name = cfg["collection"]

        if target not in found_targets:
            # Required columns are already handled above; reaching here
            # means this is an optional column that is simply absent.
            result.collections.append(CollectionResult(
                collection_name=coll_name,
                status="skipped",
                reason=f"Column '{target}' not found in uploaded file.",
            ))
            continue

        try:
            count = build_collection(
                client=client,
                embedding_fn=embedding_fn,
                collection_name=coll_name,
                target_key=target,
                rows=rows,
                metadata_keys=cfg["metadata_keys"],
            )
            result.collections.append(CollectionResult(
                collection_name=coll_name,
                status="created",
                doc_count=count,
            ))
        except Exception as exc:
            result.collections.append(CollectionResult(
                collection_name=coll_name,
                status="error",
                reason=str(exc),
            ))

    return result
