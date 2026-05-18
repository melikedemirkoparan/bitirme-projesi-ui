from fastapi import APIRouter, File, HTTPException, UploadFile

from app.ingestion.chroma_client import get_chroma_client
from app.ingestion.ingest_service import COLLECTION_CONFIGS, run_ingestion
from app.schemas.ingestion import (
    CollectionInfo,
    CollectionResultResponse,
    IngestResponse,
    IngestStatusResponse,
)

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])

_ALLOWED_EXTENSIONS = {".xlsx", ".xls"}


@router.get("/status", response_model=IngestStatusResponse)
def ingestion_status() -> IngestStatusResponse:
    """
    Return the current state of the ChromaDB collections.
    Used by the workspace on load to restore the navbar badge.
    """
    try:
        client = get_chroma_client()
        existing = {c.name: c for c in client.list_collections()}
    except Exception:
        return IngestStatusResponse(has_data=False)

    known_names = {cfg["collection"] for cfg in COLLECTION_CONFIGS}
    infos: list[CollectionInfo] = []
    for name, coll in existing.items():
        if name in known_names:
            try:
                count = coll.count()
            except Exception:
                count = 0
            infos.append(CollectionInfo(name=name, doc_count=count))

    # Only consider data "loaded" if at least one collection has documents
    has_data = any(info.doc_count > 0 for info in infos)
    return IngestStatusResponse(has_data=has_data, collections=infos)


@router.post("/upload", response_model=IngestResponse)
def upload_excel(file: UploadFile = File(...)) -> IngestResponse:
    """
    Accept an Excel file, rebuild the ChromaDB vector collections, and
    return a summary of what was created or skipped.

    The endpoint is synchronous — FastAPI runs it in a thread pool so
    the heavy embedding work does not block the event loop.
    """
    # Validate file extension before reading bytes
    filename = file.filename or ""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Please upload an .xlsx or .xls file.",
        )

    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    result = run_ingestion(file_bytes, filename)

    return IngestResponse(
        filename=result.filename,
        success=result.success,
        error=result.error,
        collections=[
            CollectionResultResponse(
                collection_name=cr.collection_name,
                status=cr.status,
                doc_count=cr.doc_count,
                reason=cr.reason,
            )
            for cr in result.collections
        ],
    )
