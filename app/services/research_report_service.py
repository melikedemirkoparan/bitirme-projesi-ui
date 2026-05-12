"""Service layer for the Research Report section.

Manages the structured text fields captured from the Patent Inputs panel,
plus uploaded research-report source documents. Files are stored on the
local filesystem under
    {settings.uploads_path}/research_report/{patent_id}/
and metadata is tracked in the research_report_document table.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.patent import Patent
from app.models.research_report import ResearchReport, ResearchReportDocument


def _patent_upload_dir(patent_id: int) -> Path:
    base = Path(settings.uploads_path) / "research_report" / str(patent_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _ensure(db: Session, patent_id: int) -> ResearchReport | None:
    patent = db.query(Patent).filter(Patent.patent_id == patent_id).first()
    if not patent:
        return None
    report = (
        db.query(ResearchReport)
        .filter(ResearchReport.patent_id == patent_id)
        .first()
    )
    if report is None:
        report = ResearchReport(patent_id=patent_id)
        db.add(report)
        db.commit()
        db.refresh(report)
    return report


def get_research_report(db: Session, patent_id: int) -> ResearchReport | None:
    return _ensure(db, patent_id)


def update_research_report(
    db: Session,
    patent_id: int,
    executive_summary: str | None,
    search_strategy: str | None,
    classification_and_keywords: str | None,
    element_patent_analysis: str | None,
) -> ResearchReport | None:
    report = _ensure(db, patent_id)
    if report is None:
        return None
    report.executive_summary = executive_summary
    report.search_strategy = search_strategy
    report.classification_and_keywords = classification_and_keywords
    report.element_patent_analysis = element_patent_analysis
    db.commit()
    db.refresh(report)
    return report


def add_document(
    db: Session,
    patent_id: int,
    original_filename: str,
    file_bytes: bytes,
    mime_type: str | None,
) -> ResearchReportDocument | None:
    report = _ensure(db, patent_id)
    if report is None:
        return None

    upload_dir = _patent_upload_dir(patent_id)
    suffix = Path(original_filename).suffix
    stored_name = f"{secrets.token_hex(8)}{suffix}"
    target = upload_dir / stored_name
    target.write_bytes(file_bytes)

    doc = ResearchReportDocument(
        research_report_id=report.research_report_id,
        original_filename=original_filename,
        stored_filename=stored_name,
        mime_type=mime_type,
        size_bytes=len(file_bytes),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_document(
    db: Session, patent_id: int, document_id: int
) -> tuple[ResearchReportDocument, Path] | None:
    doc = (
        db.query(ResearchReportDocument)
        .join(
            ResearchReport,
            ResearchReport.research_report_id
            == ResearchReportDocument.research_report_id,
        )
        .filter(
            ResearchReport.patent_id == patent_id,
            ResearchReportDocument.document_id == document_id,
        )
        .first()
    )
    if doc is None:
        return None
    path = _patent_upload_dir(patent_id) / doc.stored_filename
    if not path.exists():
        return None
    return doc, path


def get_latest_document(
    db: Session, patent_id: int
) -> tuple[ResearchReportDocument, Path] | None:
    """Return the most recently uploaded Research Report document for this patent."""
    report = _ensure(db, patent_id)
    if report is None:
        return None
    doc = (
        db.query(ResearchReportDocument)
        .filter(
            ResearchReportDocument.research_report_id == report.research_report_id
        )
        .order_by(ResearchReportDocument.created_at.desc())
        .first()
    )
    if doc is None:
        return None
    path = _patent_upload_dir(patent_id) / doc.stored_filename
    if not path.exists():
        return None
    return doc, path


def delete_document(db: Session, patent_id: int, document_id: int) -> bool:
    result = get_document(db, patent_id, document_id)
    if result is None:
        return False
    doc, path = result
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    db.delete(doc)
    db.commit()
    return True
