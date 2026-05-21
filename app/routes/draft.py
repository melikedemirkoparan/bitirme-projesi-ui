"""Patent Draft Composer route.

Spec: docs/patent_draft_composer.md

POST /api/patents/{patent_id}/draft/generate
    Assemble a full patent draft from the project's claims and context.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.generation.llm_client import LLMConnectionError
from app.schemas.draft import DraftGenerateRequest, DraftGenerateResponse
from app.services import draft_composer_service

router = APIRouter(prefix="/api/patents/{patent_id}/draft", tags=["draft"])


@router.post("/generate", response_model=DraftGenerateResponse)
def generate_draft(
    patent_id: int,
    req: DraftGenerateRequest,
    db: Session = Depends(get_db),
):
    try:
        result = draft_composer_service.generate_draft(db, patent_id, req.claims_text)
    except LLMConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "LLM'e ulaşılamadı. Colab not defterinin çalıştığını ve "
                "Settings'teki LLM API URL'sinin güncel olduğunu kontrol edin "
                "(ya da yerel Ollama'yı başlatın). Ayrıntı: " + str(exc)
            ),
        )

    if result is None:
        raise HTTPException(status_code=404, detail="Patent bulunamadı.")
    if result.get("error") == "no_claims":
        raise HTTPException(
            status_code=400,
            detail=(
                "Bu projede taslak üretmek için istem (claim) bulunamadı. "
                "Önce en az bir istem ekleyin."
            ),
        )
    return result
