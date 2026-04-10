from datetime import datetime

from pydantic import BaseModel


class ElementCreate(BaseModel):
    element_name: str
    reference_number: int | None = None
    definition_text: str | None = None


class ElementUpdate(BaseModel):
    element_name: str | None = None
    reference_number: int | None = None
    definition_text: str | None = None


class ElementResponse(BaseModel):
    element_id: int
    patent_id: int
    element_name: str
    reference_number: int | None
    definition_text: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ElementLinkResponse(BaseModel):
    """One claim that an element is linked to, with its local slot (order_index)."""
    claim_id: int
    claim_number: int
    order_index: int
