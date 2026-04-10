from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ClaimElementLink(BaseModel):
    element_id: int


class ClaimElementReorder(BaseModel):
    direction: Literal["up", "down"]


class ClaimElementResponse(BaseModel):
    claim_element_id: int
    claim_id: int
    element_id: int
    order_index: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
