from __future__ import annotations
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.schemas.claim import ClaimCreate, ClaimTextUpdate


def list_claims(db: Session, patent_id: int) -> list[Claim]:
    return (
        db.query(Claim)
        .filter(Claim.patent_id == patent_id)
        .order_by(Claim.claim_number)
        .all()
    )


def get_claim(db: Session, claim_id: int) -> Claim | None:
    return db.query(Claim).filter(Claim.claim_id == claim_id).first()


def get_claim_for_patent(db: Session, patent_id: int, claim_id: int) -> Claim | None:
    """Return the claim only if it belongs to the given patent."""
    return (
        db.query(Claim)
        .filter(Claim.claim_id == claim_id, Claim.patent_id == patent_id)
        .first()
    )


def create_claim(db: Session, patent_id: int, data: ClaimCreate) -> Claim:
    # Validate parent claim for dependent claims
    if data.claim_dependency_type == "dependent":
        parent = get_claim(db, data.parent_claim_id)
        if not parent:
            raise ValueError(f"Parent claim {data.parent_claim_id} does not exist")
        if parent.patent_id != patent_id:
            raise ValueError("Parent claim does not belong to this patent")

    # Assign the next claim number as max existing + 1.
    # Claim numbers are not renumbered after deletions — they reflect creation order,
    # not a contiguous sequence. Gaps may appear after claims are deleted.
    max_num = db.query(func.max(Claim.claim_number)).filter(Claim.patent_id == patent_id).scalar()
    next_number = (max_num or 0) + 1

    claim = Claim(
        patent_id=patent_id,
        claim_number=next_number,
        claim_dependency_type=data.claim_dependency_type,
        claim_category=data.claim_category,
        parent_claim_id=data.parent_claim_id,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def update_claim_text(db: Session, patent_id: int, claim_id: int, data: ClaimTextUpdate) -> Claim | None:
    claim = get_claim_for_patent(db, patent_id, claim_id)
    if not claim:
        return None
    claim.claim_text = data.claim_text
    db.commit()
    db.refresh(claim)
    return claim


def delete_claim(db: Session, patent_id: int, claim_id: int) -> bool:
    claim = get_claim_for_patent(db, patent_id, claim_id)
    if not claim:
        return False

    # Intentional product rule: deleting a claim recursively deletes all claims
    # that depend on it. A dependent claim without a valid parent is an invalid
    # state that cannot be corrected without knowing the correct replacement parent.
    _delete_dependents(db, claim_id)

    db.delete(claim)
    db.commit()
    return True


def _delete_dependents(db: Session, parent_claim_id: int) -> None:
    """Recursively delete all claims that depend on the given claim."""
    children = (
        db.query(Claim)
        .filter(Claim.parent_claim_id == parent_claim_id)
        .all()
    )
    for child in children:
        _delete_dependents(db, child.claim_id)
        db.delete(child)
