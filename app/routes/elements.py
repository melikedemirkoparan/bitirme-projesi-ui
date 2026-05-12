from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import definition_pipeline
from app.database import get_db
from app.schemas.element import ElementCreate, ElementLinkResponse, ElementResponse, ElementUpdate
from app.services import element_service
from app.services import patent_service

router = APIRouter(prefix="/api/patents/{patent_id}/elements", tags=["elements"])


def _get_patent_or_404(patent_id: int, db: Session):
    patent = patent_service.get_patent(db, patent_id)
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")
    return patent


@router.get("", response_model=list[ElementResponse])
def list_elements(patent_id: int, db: Session = Depends(get_db)):
    _get_patent_or_404(patent_id, db)
    return element_service.list_elements(db, patent_id)


@router.post("", response_model=ElementResponse, status_code=201)
def create_element(patent_id: int, data: ElementCreate, db: Session = Depends(get_db)):
    _get_patent_or_404(patent_id, db)
    return element_service.create_element(db, patent_id, data)


@router.patch("/{element_id}", response_model=ElementResponse)
def update_element(patent_id: int, element_id: int, data: ElementUpdate, db: Session = Depends(get_db)):
    _get_patent_or_404(patent_id, db)
    try:
        element = element_service.update_element(db, patent_id, element_id, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not element:
        raise HTTPException(status_code=404, detail="Element not found")
    return element


@router.get("/{element_id}/links", response_model=list[ElementLinkResponse])
def list_element_links(patent_id: int, element_id: int, db: Session = Depends(get_db)):
    """Return all claims this element is linked to, with the local slot (order_index)."""
    _get_patent_or_404(patent_id, db)
    el = element_service.get_element_for_patent(db, patent_id, element_id)
    if not el:
        raise HTTPException(status_code=404, detail="Element not found")
    return element_service.list_claims_for_element(db, patent_id, element_id)


@router.delete("/{element_id}", status_code=204)
def delete_element(patent_id: int, element_id: int, db: Session = Depends(get_db)):
    _get_patent_or_404(patent_id, db)
    if not element_service.delete_element(db, patent_id, element_id):
        raise HTTPException(status_code=404, detail="Element not found")


@router.post("/{element_id}/generate-definition")
def generate_definition_for_element(
    patent_id: int,
    element_id: int,
    top_k: int = 5,
    db: Session = Depends(get_db),
):
    """Run the 3-stage definition pipeline for one element.

    Pulls structured project inputs (invention disclosure, research report,
    inventor Q&A), the related-elements list, and RAG hits from the project's
    state, then returns a single candidate definition plus per-stage outputs.
    """
    _get_patent_or_404(patent_id, db)
    result = definition_pipeline.generate_definition(
        db, patent_id, element_id, top_k=top_k
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Element not found")
    return result
