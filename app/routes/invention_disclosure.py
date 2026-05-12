"""Invention Disclosure (BBF) routes for the Patent Inputs panel."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.invention_disclosure import (
    InventionDisclosureRead,
    InventionDisclosureUpdate,
)
from app.services import invention_disclosure_service

router = APIRouter(
    prefix="/api/patents/{patent_id}/invention-disclosure",
    tags=["invention_disclosure"],
)


@router.get("", response_model=InventionDisclosureRead)
def read_invention_disclosure(patent_id: int, db: Session = Depends(get_db)):
    idf = invention_disclosure_service.get_invention_disclosure(db, patent_id)
    if idf is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    return idf


@router.put("", response_model=InventionDisclosureRead)
def update_invention_disclosure(
    patent_id: int,
    data: InventionDisclosureUpdate,
    db: Session = Depends(get_db),
):
    # Treat the PUT as a partial update. Only the fields the client
    # actually included are forwarded — Pydantic gives us None for both
    # "omitted" and explicit-null, so we use `model_fields_set` to tell
    # them apart. This prevents the Settings modal (which only sends
    # bbf_text) from clobbering the structured fields the Patent Inputs
    # panel had previously saved.
    kwargs = {}
    for field in ("prior_art_and_problems", "closest_prior_patents", "novel_features", "bbf_text"):
        if field in data.model_fields_set:
            kwargs[field] = getattr(data, field)
    if not kwargs:
        # Nothing to update — return current state.
        idf = invention_disclosure_service.get_invention_disclosure(db, patent_id)
        if idf is None:
            raise HTTPException(status_code=404, detail="Patent not found")
        return idf
    idf = invention_disclosure_service.update_invention_disclosure(
        db, patent_id, **kwargs
    )
    if idf is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    return idf


@router.post("/documents", response_model=InventionDisclosureRead, status_code=201)
def upload_invention_disclosure_document(
    patent_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    doc = invention_disclosure_service.add_document(
        db,
        patent_id,
        original_filename=file.filename or "document",
        file_bytes=file_bytes,
        mime_type=file.content_type,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    return invention_disclosure_service.get_invention_disclosure(db, patent_id)


@router.get("/documents/{document_id}")
def download_invention_disclosure_document(
    patent_id: int, document_id: int, db: Session = Depends(get_db)
):
    result = invention_disclosure_service.get_document(db, patent_id, document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc, path = result
    return FileResponse(
        path=str(path),
        filename=doc.original_filename,
        media_type=doc.mime_type or "application/octet-stream",
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_invention_disclosure_document(
    patent_id: int, document_id: int, db: Session = Depends(get_db)
):
    if not invention_disclosure_service.delete_document(db, patent_id, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
