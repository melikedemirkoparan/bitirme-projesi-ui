"""
Service layer for the Inventor_QA (Buluşçu ile Yazışmalar) section.

Manages the free-text Q&A field plus uploaded clarification documents.
Files are stored on the local filesystem under
    {settings.uploads_path}/inventor_qa/{patent_id}/
and metadata is tracked in the inventor_qa_document table.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.inventor_qa import InventorQA, InventorQADocument
from app.models.patent import Patent


def _patent_upload_dir(patent_id: int) -> Path:
    base = Path(settings.uploads_path) / "inventor_qa" / str(patent_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _ensure_inventor_qa(db: Session, patent_id: int) -> InventorQA | None:
    patent = db.query(Patent).filter(Patent.patent_id == patent_id).first()
    if not patent:
        return None
    qa = (
        db.query(InventorQA)
        .filter(InventorQA.patent_id == patent_id)
        .first()
    )
    if qa is None:
        qa = InventorQA(patent_id=patent_id, questions_and_answers=None)
        db.add(qa)
        db.commit()
        db.refresh(qa)
    return qa


def get_inventor_qa(db: Session, patent_id: int) -> InventorQA | None:
    return _ensure_inventor_qa(db, patent_id)


def update_inventor_qa_text(
    db: Session, patent_id: int, questions_and_answers: str | None
) -> InventorQA | None:
    qa = _ensure_inventor_qa(db, patent_id)
    if qa is None:
        return None
    qa.questions_and_answers = questions_and_answers
    db.commit()
    db.refresh(qa)
    return qa


def add_document(
    db: Session,
    patent_id: int,
    original_filename: str,
    file_bytes: bytes,
    mime_type: str | None,
) -> InventorQADocument | None:
    qa = _ensure_inventor_qa(db, patent_id)
    if qa is None:
        return None

    upload_dir = _patent_upload_dir(patent_id)
    suffix = Path(original_filename).suffix
    stored_name = f"{secrets.token_hex(8)}{suffix}"
    target = upload_dir / stored_name
    target.write_bytes(file_bytes)

    doc = InventorQADocument(
        qna_id=qa.qna_id,
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
) -> tuple[InventorQADocument, Path] | None:
    doc = (
        db.query(InventorQADocument)
        .join(InventorQA, InventorQA.qna_id == InventorQADocument.qna_id)
        .filter(
            InventorQA.patent_id == patent_id,
            InventorQADocument.document_id == document_id,
        )
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
