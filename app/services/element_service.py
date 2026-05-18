from __future__ import annotations
from sqlalchemy.orm import Session

from app.models.element import Element
from app.schemas.element import ElementCreate, ElementUpdate


def list_elements(db: Session, patent_id: int) -> list[Element]:
    return (
        db.query(Element)
        .filter(Element.patent_id == patent_id)
        .order_by(Element.created_at)
        .all()
    )


def get_element(db: Session, element_id: int) -> Element | None:
    return db.query(Element).filter(Element.element_id == element_id).first()


def get_element_for_patent(db: Session, patent_id: int, element_id: int) -> Element | None:
    """Return the element only if it belongs to the given patent."""
    return (
        db.query(Element)
        .filter(Element.element_id == element_id, Element.patent_id == patent_id)
        .first()
    )


def _next_reference_number(db: Session, patent_id: int) -> str:
    """Pick the next sequential numeric reference_number for this patent.

    Scans existing reference_numbers, finds the highest purely-numeric one,
    and returns max+1 as a string. Non-numeric refs (e.g. user-typed "A1")
    are ignored. Falls back to "1" when no numeric refs exist yet.
    """
    existing = (
        db.query(Element.reference_number)
        .filter(Element.patent_id == patent_id)
        .all()
    )
    max_n = 0
    for (ref,) in existing:
        if ref and ref.isdigit():
            n = int(ref)
            if n > max_n:
                max_n = n
    return str(max_n + 1)


def create_element(db: Session, patent_id: int, data: ElementCreate) -> Element:
    reference_number = data.reference_number or _next_reference_number(db, patent_id)
    element = Element(
        patent_id=patent_id,
        element_name=data.element_name,
        reference_number=reference_number,
        definition_text=data.definition_text,
    )
    db.add(element)
    db.commit()
    db.refresh(element)
    return element


def update_element(db: Session, patent_id: int, element_id: int, data: ElementUpdate) -> Element | None:
    element = get_element_for_patent(db, patent_id, element_id)
    if not element:
        return None

    # Use model_fields_set to apply only fields that were explicitly included in the request.
    # This distinguishes between an omitted field (leave unchanged) and an explicitly sent
    # null (allowed to clear nullable fields like definition_text).
    for field in data.model_fields_set:
        value = getattr(data, field)
        # reference_number is NOT NULL in the DB; reject explicit nulls at the boundary.
        if field == "reference_number" and value is None:
            raise ValueError("reference_number cannot be set to null")
        setattr(element, field, value)

    db.commit()
    db.refresh(element)
    return element


def delete_element(db: Session, patent_id: int, element_id: int) -> bool:
    element = get_element_for_patent(db, patent_id, element_id)
    if not element:
        return False
    db.delete(element)
    db.commit()
    return True


def list_claims_for_element(db: Session, patent_id: int, element_id: int) -> list[dict]:
    """Return all claims that this element is linked to, with the local slot (order_index)."""
    from app.models.claim import Claim
    from app.models.claim_element import ClaimElement

    element = get_element_for_patent(db, patent_id, element_id)
    if not element:
        return []

    rows = (
        db.query(ClaimElement, Claim)
        .join(Claim, Claim.claim_id == ClaimElement.claim_id)
        .filter(
            ClaimElement.element_id == element_id,
            Claim.patent_id == patent_id,
        )
        .order_by(Claim.claim_number, ClaimElement.order_index)
        .all()
    )

    return [
        {"claim_id": ce.claim_id, "claim_number": c.claim_number, "order_index": ce.order_index}
        for ce, c in rows
    ]
