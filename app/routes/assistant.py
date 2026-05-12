from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.assistant import AssistantRequest, AssistantResponse
from app.services import assistant_service

router = APIRouter(prefix="/api/patents", tags=["assistant"])


@router.post("/{patent_id}/assistant/ask", response_model=AssistantResponse)
def ask(patent_id: int, req: AssistantRequest, db: Session = Depends(get_db)):
    result = assistant_service.ask(db, patent_id, req)
    if result is None:
        raise HTTPException(status_code=404, detail="Patent not found.")
    return result
