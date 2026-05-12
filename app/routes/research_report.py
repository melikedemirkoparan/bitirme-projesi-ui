"""Research Report routes for the Patent Inputs panel."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.research_report import (
    ResearchReportRead,
    ResearchReportUpdate,
)
from app.services import research_report_service

router = APIRouter(
    prefix="/api/patents/{patent_id}/research-report",
    tags=["research_report"],
)


@router.get("", response_model=ResearchReportRead)
def read_research_report(patent_id: int, db: Session = Depends(get_db)):
    report = research_report_service.get_research_report(db, patent_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    return report


@router.put("", response_model=ResearchReportRead)
def update_research_report(
    patent_id: int,
    data: ResearchReportUpdate,
    db: Session = Depends(get_db),
):
    report = research_report_service.update_research_report(
        db,
        patent_id,
        executive_summary=data.executive_summary,
        search_strategy=data.search_strategy,
        classification_and_keywords=data.classification_and_keywords,
        element_patent_analysis=data.element_patent_analysis,
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    return report


@router.post("/documents", response_model=ResearchReportRead, status_code=201)
def upload_research_report_document(
    patent_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    doc = research_report_service.add_document(
        db,
        patent_id,
        original_filename=file.filename or "document",
        file_bytes=file_bytes,
        mime_type=file.content_type,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    return research_report_service.get_research_report(db, patent_id)


@router.get("/documents/{document_id}")
def download_research_report_document(
    patent_id: int, document_id: int, db: Session = Depends(get_db)
):
    result = research_report_service.get_document(db, patent_id, document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc, path = result
    return FileResponse(
        path=str(path),
        filename=doc.original_filename,
        media_type=doc.mime_type or "application/octet-stream",
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_research_report_document(
    patent_id: int, document_id: int, db: Session = Depends(get_db)
):
    if not research_report_service.delete_document(db, patent_id, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
