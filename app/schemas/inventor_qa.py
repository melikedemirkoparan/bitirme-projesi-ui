from datetime import datetime

from pydantic import BaseModel


class InventorQADocumentRead(BaseModel):
    document_id: int
    original_filename: str
    mime_type: str | None = None
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class InventorQARead(BaseModel):
    qna_id: int
    patent_id: int
    questions_and_answers: str | None = None
    created_at: datetime
    updated_at: datetime
    documents: list[InventorQADocumentRead] = []

    model_config = {"from_attributes": True}


class InventorQAUpdate(BaseModel):
    questions_and_answers: str | None = None
