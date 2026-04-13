"""
Inventor_QA (Buluşçu ile Yazışmalar) routes.

Exposes the patent-scoped Q&A text plus document upload/list/download/delete
operations consumed by the frontend Patent Inputs panel.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.inventor_qa import InventorQARead, InventorQAUpdate
from app.services import inventor_qa_service

router = APIRouter(prefix="/api/patents/{patent_id}/inventor-qa", tags=["inventor_qa"])


@router.get("", response_model=InventorQARead)
def read_inventor_qa(patent_id: int, db: Session = Depends(get_db)):
    qa = inventor_qa_service.get_inventor_qa(db, patent_id)
    if qa is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    return qa


@router.put("", response_model=InventorQARead)
def update_inventor_qa(
    patent_id: int, data: InventorQAUpdate, db: Session = Depends(get_db)
):
    qa = inventor_qa_service.update_inventor_qa_text(
        db, patent_id, data.questions_and_answers
    )
    if qa is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    return qa


@router.post("/documents", response_model=InventorQARead, status_code=201)
def upload_inventor_qa_document(
    patent_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    doc = inventor_qa_service.add_document(
        db,
        patent_id,
        original_filename=file.filename or "document",
        file_bytes=file_bytes,
        mime_type=file.content_type,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    qa = inventor_qa_service.get_inventor_qa(db, patent_id)
    return qa


@router.get("/documents/{document_id}")
def download_inventor_qa_document(
    patent_id: int, document_id: int, db: Session = Depends(get_db)
):
    result = inventor_qa_service.get_document(db, patent_id, document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc, path = result
    return FileResponse(
        path=str(path),
        filename=doc.original_filename,
        media_type=doc.mime_type or "application/octet-stream",
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_inventor_qa_document(
    patent_id: int, document_id: int, db: Session = Depends(get_db)
):
    if not inventor_qa_service.delete_document(db, patent_id, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
