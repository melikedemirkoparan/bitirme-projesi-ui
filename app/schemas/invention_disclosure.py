from datetime import datetime

from pydantic import BaseModel


class InventionDisclosureDocumentRead(BaseModel):
    document_id: int
    original_filename: str
    mime_type: str | None = None
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class InventionDisclosureRead(BaseModel):
    idf_id: int
    patent_id: int
    prior_art_and_problems: str | None = None
    closest_prior_patents: str | None = None
    novel_features: str | None = None
    bbf_text: str | None = None
    created_at: datetime
    updated_at: datetime
    documents: list[InventionDisclosureDocumentRead] = []

    model_config = {"from_attributes": True}


class InventionDisclosureUpdate(BaseModel):
    prior_art_and_problems: str | None = None
    closest_prior_patents: str | None = None
    novel_features: str | None = None
    bbf_text: str | None = None
