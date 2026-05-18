from __future__ import annotations
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.claim_element import ClaimElement
from app.models.element import Element
from app.schemas.claim import ClaimCreate, ClaimDraftRequest, ClaimDraftResult, ClaimTextUpdate, ClaimUpdate


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
    # Validate parent claims for dependent claims
    if data.claim_dependency_type == "dependent":
        for pid in data.parent_claim_ids:
            parent = get_claim(db, pid)
            if not parent:
                raise ValueError(f"Parent claim {pid} does not exist")
            if parent.patent_id != patent_id:
                raise ValueError(f"Parent claim {pid} does not belong to this patent")

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
        parent_claim_ids=data.parent_claim_ids,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def update_claim(db: Session, patent_id: int, claim_id: int, data: ClaimUpdate) -> Claim | None:
    claim = get_claim_for_patent(db, patent_id, claim_id)
    if not claim:
        return None
    if data.claim_dependency_type is not None:
        claim.claim_dependency_type = data.claim_dependency_type
    if data.claim_category is not None:
        claim.claim_category = data.claim_category
    if data.parent_claim_ids is not None:
        if data.claim_dependency_type == "dependent" or claim.claim_dependency_type == "dependent":
            for pid in data.parent_claim_ids:
                parent = get_claim(db, pid)
                if not parent:
                    raise ValueError(f"Parent claim {pid} does not exist")
                if parent.patent_id != patent_id:
                    raise ValueError(f"Parent claim {pid} does not belong to this patent")
        claim.parent_claim_ids = data.parent_claim_ids
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
    _delete_dependents(db, claim_id, deleted_ids={claim_id})

    db.delete(claim)
    db.commit()
    return True


# ── Claim draft generation ────────────────────────────────────────

def _get_ordered_elements(db: Session, claim_id: int) -> list[Element]:
    return (
        db.query(Element)
        .join(ClaimElement, ClaimElement.element_id == Element.element_id)
        .filter(ClaimElement.claim_id == claim_id)
        .order_by(ClaimElement.order_index, ClaimElement.claim_element_id)
        .all()
    )


def _join_defs(elements: list[Element]) -> str:
    return ", ".join(e.definition_text for e in elements)


def _parent_ref(numbers: list[int]) -> str:
    if len(numbers) == 1:
        return f"claim {numbers[0]}"
    formatted = ", ".join(str(n) for n in numbers)
    return f"any of claims {formatted}"


def _strip_indefinite_article(name: str) -> str:
    """Remove leading 'a ' or 'an ' so the name can follow 'the'."""
    for prefix in ("an ", "a "):
        if name.lower().startswith(prefix):
            return name[len(prefix):]
    return name


def _build_independent_apparatus(
    elements: list[Element], group_b_ids: set[int], system_name: str
) -> str:
    group_a = [e for e in elements if e.element_id not in group_b_ids]
    group_b = [e for e in elements if e.element_id in group_b_ids]
    part_a, part_b = _join_defs(group_a), _join_defs(group_b)
    bare_name = _strip_indefinite_article(system_name)
    if not part_a and not part_b:
        return ""
    if part_a and part_b:
        return (
            f"{system_name} comprising {part_a}; "
            f"characterized in that the {bare_name} further comprises {part_b}."
        )
    if part_b:
        return f"{system_name} characterized in that it comprises {part_b}."
    return f"{system_name} comprising {part_a}."


def _build_dependent_apparatus(
    elements: list[Element], system_name: str, parent_ref: str
) -> str:
    return (
        f"{system_name} according to {parent_ref}, "
        f"further comprising {_join_defs(elements)}."
    )


def _build_independent_method(elements: list[Element], purpose: str) -> str:
    return f"A method for {purpose}, the method comprising {_join_defs(elements)}."


def _build_dependent_method(elements: list[Element], purpose: str, parent_ref: str) -> str:
    return (
        f"A method according to {parent_ref}, "
        f"further comprising {_join_defs(elements)}."
    )


def generate_claim_draft(
    db: Session, patent_id: int, claim_id: int, data: ClaimDraftRequest
) -> ClaimDraftResult:
    claim = get_claim_for_patent(db, patent_id, claim_id)
    if not claim:
        return ClaimDraftResult(
            claim_id=claim_id, claim_number=0,
            claim_dependency_type="", claim_category="",
            success=False, warning="Claim not found.",
        )

    elements = _get_ordered_elements(db, claim_id)
    if not elements:
        return ClaimDraftResult(
            claim_id=claim_id, claim_number=claim.claim_number,
            claim_dependency_type=claim.claim_dependency_type,
            claim_category=claim.claim_category,
            success=False, warning="No elements linked to this claim.",
        )

    missing = [e.element_name for e in elements if not e.definition_text]
    if missing:
        return ClaimDraftResult(
            claim_id=claim_id, claim_number=claim.claim_number,
            claim_dependency_type=claim.claim_dependency_type,
            claim_category=claim.claim_category,
            success=False, warning=f"Missing definitions for: {', '.join(missing)}.",
        )

    dep, cat = claim.claim_dependency_type, claim.claim_category

    # Resolve parent claim numbers — request override takes priority,
    # then fall back to the claim's stored parent_claim_ids.
    parent_numbers = data.parent_claim_numbers
    if not parent_numbers:
        stored_ids = claim.parent_claim_ids or []
        if stored_ids:
            parents = (
                db.query(Claim)
                .filter(Claim.claim_id.in_(stored_ids))
                .order_by(Claim.claim_number)
                .all()
            )
            parent_numbers = [p.claim_number for p in parents]

    # For dependent claims, parent reference is mandatory.
    if dep == "dependent" and not parent_numbers:
        return ClaimDraftResult(
            claim_id=claim_id, claim_number=claim.claim_number,
            claim_dependency_type=dep, claim_category=cat,
            success=False, warning="Could not resolve parent claim number.",
        )

    parent_ref = _parent_ref(parent_numbers) if parent_numbers else ""
    system_name = data.system_name.strip() or "the system"
    purpose = data.method_purpose.strip() or system_name

    if dep == "independent" and cat == "apparatus":
        text = _build_independent_apparatus(elements, set(data.group_b_element_ids), system_name)
    elif dep == "dependent" and cat == "apparatus":
        text = _build_dependent_apparatus(elements, system_name, parent_ref)
    elif dep == "independent" and cat == "method":
        text = _build_independent_method(elements, purpose)
    else:
        text = _build_dependent_method(elements, purpose, parent_ref)

    if not text:
        return ClaimDraftResult(
            claim_id=claim_id, claim_number=claim.claim_number,
            claim_dependency_type=dep, claim_category=cat,
            success=False, warning="Could not generate claim text.",
        )

    return ClaimDraftResult(
        claim_id=claim_id, claim_number=claim.claim_number,
        claim_dependency_type=dep, claim_category=cat,
        success=True, claim_text=text,
    )


def _delete_dependents(db: Session, parent_claim_id: int, deleted_ids: set[int]) -> None:
    """Recursively delete claims whose ALL parents are being deleted.

    deleted_ids accumulates every claim ID that will be removed in this
    cascade pass. A child is only deleted when every one of its parent
    IDs is in deleted_ids — keeping it alive if any parent survives.
    """
    all_claims = db.query(Claim).all()
    children = [c for c in all_claims if parent_claim_id in (c.parent_claim_ids or [])]
    for child in children:
        remaining = set(child.parent_claim_ids or []) - deleted_ids
        if not remaining:
            deleted_ids.add(child.claim_id)
            _delete_dependents(db, child.claim_id, deleted_ids)
            db.delete(child)
