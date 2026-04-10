from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.claim_element import ClaimElement
from app.models.element import Element


def list_elements_for_claim(db: Session, patent_id: int, claim_id: int) -> list[Element]:
    """
    Return all elements linked to the given claim.
    The claim must belong to the given patent for consistency with other patent-scoped services.
    Returns Element objects — routes should use ElementResponse for serialization.
    """
    from app.services.claim_service import get_claim_for_patent
    claim = get_claim_for_patent(db, patent_id, claim_id)
    if not claim:
        return []

    return (
        db.query(Element)
        .join(ClaimElement, ClaimElement.element_id == Element.element_id)
        .filter(ClaimElement.claim_id == claim_id)
        .order_by(ClaimElement.order_index, ClaimElement.claim_element_id)
        .all()
    )


def _get_link(db: Session, claim_id: int, element_id: int) -> ClaimElement | None:
    return (
        db.query(ClaimElement)
        .filter(ClaimElement.claim_id == claim_id, ClaimElement.element_id == element_id)
        .first()
    )


def link_element_to_claim(
    db: Session, patent_id: int, claim_id: int, element_id: int
) -> ClaimElement:
    """
    Link an element to a claim. Both must belong to the given patent.
    Idempotent: linking the same element twice returns the existing link.
    """
    from app.services.claim_service import get_claim_for_patent
    from app.services.element_service import get_element_for_patent

    claim = get_claim_for_patent(db, patent_id, claim_id)
    if not claim:
        raise ValueError("Claim not found or does not belong to this patent")

    element = get_element_for_patent(db, patent_id, element_id)
    if not element:
        raise ValueError("Element not found or does not belong to this patent")

    existing = _get_link(db, claim_id, element_id)
    if existing:
        return existing

    max_order = (
        db.query(func.max(ClaimElement.order_index))
        .filter(ClaimElement.claim_id == claim_id)
        .scalar()
    )
    next_order = (max_order or 0) + 1

    link = ClaimElement(
        claim_id=claim_id,
        element_id=element_id,
        order_index=next_order,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def reorder_element_in_claim(
    db: Session, patent_id: int, claim_id: int, element_id: int, direction: str
) -> bool:
    """
    Move an element one position up or down within a claim's ordered element list.
    Swaps order_index values with the adjacent link in the requested direction.
    Returns False (no-op) if the element is already at the boundary.
    """
    from app.services.claim_service import get_claim_for_patent
    from app.services.element_service import get_element_for_patent

    claim = get_claim_for_patent(db, patent_id, claim_id)
    if not claim:
        return False

    element = get_element_for_patent(db, patent_id, element_id)
    if not element:
        return False

    link = _get_link(db, claim_id, element_id)
    if not link:
        return False

    links = (
        db.query(ClaimElement)
        .filter(ClaimElement.claim_id == claim_id)
        .order_by(ClaimElement.order_index, ClaimElement.claim_element_id)
        .all()
    )

    idx = next(
        (i for i, lnk in enumerate(links) if lnk.claim_element_id == link.claim_element_id),
        None,
    )
    if idx is None:
        return False

    if direction == "up":
        if idx == 0:
            return False
        neighbor = links[idx - 1]
    else:
        if idx == len(links) - 1:
            return False
        neighbor = links[idx + 1]

    link.order_index, neighbor.order_index = neighbor.order_index, link.order_index
    db.commit()
    return True


def unlink_element_from_claim(
    db: Session, patent_id: int, claim_id: int, element_id: int
) -> bool:
    """
    Remove the link between an element and a claim.
    Validates claim ownership against the patent before proceeding.
    """
    from app.services.claim_service import get_claim_for_patent

    claim = get_claim_for_patent(db, patent_id, claim_id)
    if not claim:
        return False

    link = _get_link(db, claim_id, element_id)
    if not link:
        return False

    db.delete(link)
    db.flush()

    remaining_links = (
        db.query(ClaimElement)
        .filter(ClaimElement.claim_id == claim_id)
        .order_by(ClaimElement.order_index, ClaimElement.claim_element_id)
        .all()
    )
    for idx, remaining_link in enumerate(remaining_links, start=1):
        remaining_link.order_index = idx

    db.commit()
    return True
