from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.claim import ClaimCreate, ClaimDraftRequest, ClaimDraftResult, ClaimResponse, ClaimTextUpdate, ClaimUpdate
from app.services import claim_service
from app.services import patent_service

router = APIRouter(prefix="/api/patents/{patent_id}/claims", tags=["claims"])


def _get_patent_or_404(patent_id: int, db: Session):
    patent = patent_service.get_patent(db, patent_id)
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")
    return patent


@router.get("", response_model=list[ClaimResponse])
def list_claims(patent_id: int, db: Session = Depends(get_db)):
    _get_patent_or_404(patent_id, db)
    return claim_service.list_claims(db, patent_id)


@router.post("", response_model=ClaimResponse, status_code=201)
def create_claim(patent_id: int, data: ClaimCreate, db: Session = Depends(get_db)):
    _get_patent_or_404(patent_id, db)
    try:
        return claim_service.create_claim(db, patent_id, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/{claim_id}", response_model=ClaimResponse)
def update_claim(patent_id: int, claim_id: int, data: ClaimUpdate, db: Session = Depends(get_db)):
    _get_patent_or_404(patent_id, db)
    try:
        claim = claim_service.update_claim(db, patent_id, claim_id, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.patch("/{claim_id}/text", response_model=ClaimResponse)
def update_claim_text(patent_id: int, claim_id: int, data: ClaimTextUpdate, db: Session = Depends(get_db)):
    _get_patent_or_404(patent_id, db)
    claim = claim_service.update_claim_text(db, patent_id, claim_id, data)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.delete("/{claim_id}", status_code=204)
def delete_claim(patent_id: int, claim_id: int, db: Session = Depends(get_db)):
    _get_patent_or_404(patent_id, db)
    if not claim_service.delete_claim(db, patent_id, claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")


@router.post("/{claim_id}/generate-draft", response_model=ClaimDraftResult)
def generate_claim_draft(
    patent_id: int,
    claim_id: int,
    data: ClaimDraftRequest,
    db: Session = Depends(get_db),
):
    _get_patent_or_404(patent_id, db)
    return claim_service.generate_claim_draft(db, patent_id, claim_id, data)
