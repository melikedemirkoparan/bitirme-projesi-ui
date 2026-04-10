from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.claim_element import ClaimElementLink, ClaimElementReorder, ClaimElementResponse
from app.schemas.element import ElementResponse
from app.services import claim_element_service
from app.services import patent_service

router = APIRouter(
    prefix="/api/patents/{patent_id}/claims/{claim_id}/elements",
    tags=["claim-elements"],
)


def _get_patent_or_404(patent_id: int, db: Session):
    patent = patent_service.get_patent(db, patent_id)
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")
    return patent


@router.get("", response_model=list[ElementResponse])
def list_claim_elements(patent_id: int, claim_id: int, db: Session = Depends(get_db)):
    _get_patent_or_404(patent_id, db)
    return claim_element_service.list_elements_for_claim(db, patent_id, claim_id)


@router.post("", response_model=ClaimElementResponse, status_code=201)
def link_element(
    patent_id: int, claim_id: int, data: ClaimElementLink, db: Session = Depends(get_db)
):
    _get_patent_or_404(patent_id, db)
    try:
        return claim_element_service.link_element_to_claim(db, patent_id, claim_id, data.element_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/{element_id}", status_code=204)
def reorder_element(
    patent_id: int, claim_id: int, element_id: int,
    data: ClaimElementReorder, db: Session = Depends(get_db),
):
    """Move an element up or down within a claim's ordered element list."""
    _get_patent_or_404(patent_id, db)
    moved = claim_element_service.reorder_element_in_claim(
        db, patent_id, claim_id, element_id, data.direction
    )
    if not moved:
        raise HTTPException(status_code=422, detail="Cannot move element in that direction")


@router.delete("/{element_id}", status_code=204)
def unlink_element(
    patent_id: int, claim_id: int, element_id: int, db: Session = Depends(get_db)
):
    _get_patent_or_404(patent_id, db)
    if not claim_element_service.unlink_element_from_claim(db, patent_id, claim_id, element_id):
        raise HTTPException(status_code=404, detail="Link not found")
