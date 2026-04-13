from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.patent import PatentCreate, PatentDetail, PatentSummary, PatentUpdate
from app.services import patent_service

router = APIRouter(prefix="/api/patents", tags=["patents"])


@router.get("", response_model=list[PatentSummary])
def list_patents(db: Session = Depends(get_db)):
    return patent_service.list_patents(db)


@router.get("/{patent_id}", response_model=PatentDetail)
def get_patent(patent_id: int, db: Session = Depends(get_db)):
    patent = patent_service.get_patent(db, patent_id)
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")
    return patent


@router.post("", response_model=PatentDetail, status_code=201)
def create_patent(data: PatentCreate, db: Session = Depends(get_db)):
    return patent_service.create_patent(db, data)


@router.patch("/{patent_id}", response_model=PatentDetail)
def update_patent(patent_id: int, data: PatentUpdate, db: Session = Depends(get_db)):
    patent = patent_service.update_patent(db, patent_id, data)
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")
    return patent


@router.delete("/{patent_id}", status_code=204)
def delete_patent(patent_id: int, db: Session = Depends(get_db)):
    if not patent_service.delete_patent(db, patent_id):
        raise HTTPException(status_code=404, detail="Patent not found")
