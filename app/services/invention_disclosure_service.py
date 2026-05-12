"""Service layer for the Invention Disclosure (BBF) section.

Manages the structured text fields captured from the Patent Inputs panel,
plus uploaded BBF source documents. Files are stored on the local filesystem
under
    {settings.uploads_path}/invention_disclosure/{patent_id}/
and metadata is tracked in the invention_disclosure_document table.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.invention_disclosure import (
    InventionDisclosure,
    InventionDisclosureDocument,
)
from app.models.patent import Patent


def _patent_upload_dir(patent_id: int) -> Path:
    base = Path(settings.uploads_path) / "invention_disclosure" / str(patent_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _ensure(db: Session, patent_id: int) -> InventionDisclosure | None:
    patent = db.query(Patent).filter(Patent.patent_id == patent_id).first()
    if not patent:
        return None
    idf = (
        db.query(InventionDisclosure)
        .filter(InventionDisclosure.patent_id == patent_id)
        .first()
    )
    if idf is None:
        idf = InventionDisclosure(patent_id=patent_id)
        db.add(idf)
        db.commit()
        db.refresh(idf)
    return idf


def get_invention_disclosure(
    db: Session, patent_id: int
) -> InventionDisclosure | None:
    return _ensure(db, patent_id)


_UNSET = object()


def update_invention_disclosure(
    db: Session,
    patent_id: int,
    prior_art_and_problems=_UNSET,
    closest_prior_patents=_UNSET,
    novel_features=_UNSET,
    bbf_text=_UNSET,
) -> InventionDisclosure | None:
    """Partial update of the patent's invention disclosure.

    Each field is optional — fields not passed (left at the _UNSET
    sentinel) are preserved unchanged. Pass `None` to explicitly clear
    a field. This is how the Patent Inputs panel can save the
    structured BBF fields without clobbering bbf_text, and how the
    Settings modal can save bbf_text without clobbering the structured
    fields.
    """
    idf = _ensure(db, patent_id)
    if idf is None:
        return None
    if prior_art_and_problems is not _UNSET:
        idf.prior_art_and_problems = prior_art_and_problems
    if closest_prior_patents is not _UNSET:
        idf.closest_prior_patents = closest_prior_patents
    if novel_features is not _UNSET:
        idf.novel_features = novel_features
    if bbf_text is not _UNSET:
        idf.bbf_text = bbf_text
    db.commit()
    db.refresh(idf)
    return idf


def set_bbf_text(
    db: Session, patent_id: int, bbf_text: str | None
) -> InventionDisclosure | None:
    """Set only the bbf_text field — used by the extract pipeline and
    by the Settings modal so structured fields are left untouched."""
    idf = _ensure(db, patent_id)
    if idf is None:
        return None
    idf.bbf_text = bbf_text
    db.commit()
    db.refresh(idf)
    return idf


def add_document(
    db: Session,
    patent_id: int,
    original_filename: str,
    file_bytes: bytes,
    mime_type: str | None,
) -> InventionDisclosureDocument | None:
    idf = _ensure(db, patent_id)
    if idf is None:
        return None

    upload_dir = _patent_upload_dir(patent_id)
    suffix = Path(original_filename).suffix
    stored_name = f"{secrets.token_hex(8)}{suffix}"
    target = upload_dir / stored_name
    target.write_bytes(file_bytes)

    doc = InventionDisclosureDocument(
        idf_id=idf.idf_id,
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
) -> tuple[InventionDisclosureDocument, Path] | None:
    doc = (
        db.query(InventionDisclosureDocument)
        .join(
            InventionDisclosure,
            InventionDisclosure.idf_id == InventionDisclosureDocument.idf_id,
        )
        .filter(
            InventionDisclosure.patent_id == patent_id,
            InventionDisclosureDocument.document_id == document_id,
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
) -> tuple[InventionDisclosureDocument, Path] | None:
    """Return the most recently uploaded BBF document for this patent."""
    idf = _ensure(db, patent_id)
    if idf is None:
        return None
    doc = (
        db.query(InventionDisclosureDocument)
        .filter(InventionDisclosureDocument.idf_id == idf.idf_id)
        .order_by(InventionDisclosureDocument.created_at.desc())
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
