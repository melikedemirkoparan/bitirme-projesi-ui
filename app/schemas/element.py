from __future__ import annotations
import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

REFERENCE_NUMBER_PATTERN = r"^[A-Za-z0-9'\-]{1,10}$"
_REF_HAS_ALNUM = re.compile(r"[A-Za-z0-9]")


def _validate_reference_number(value: str) -> str:
    if not _REF_HAS_ALNUM.search(value):
        raise ValueError("reference_number must contain at least one letter or digit")
    return value


class ElementCreate(BaseModel):
    element_name: str
    # Optional: when omitted (or null), the service assigns the next sequential
    # numeric reference_number for the patent. Bulk flows like Extract Elements
    # rely on this; manual adds may still pass an explicit value.
    reference_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=10,
        pattern=REFERENCE_NUMBER_PATTERN,
    )
    definition_text: str | None = None

    @field_validator("reference_number")
    @classmethod
    def _ref_alnum(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_reference_number(v)


class ElementUpdate(BaseModel):
    element_name: str | None = None
    reference_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=10,
        pattern=REFERENCE_NUMBER_PATTERN,
    )
    definition_text: str | None = None

    @field_validator("reference_number")
    @classmethod
    def _ref_alnum(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_reference_number(v)


class ElementResponse(BaseModel):
    element_id: int
    patent_id: int
    element_name: str
    reference_number: str
    definition_text: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ElementLinkResponse(BaseModel):
    """One claim that an element is linked to, with its local slot (order_index)."""
    claim_id: int
    claim_number: int
    order_index: int
