from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


# ── Create request ──────────────────────────────────────────────
# Collects the fields from the Add Claim modal (docs/claim_workspace.md).
# claim_number is assigned by the service, not the client.

class ClaimCreate(BaseModel):
    claim_dependency_type: Literal["independent", "dependent"]
    claim_category: Literal["apparatus", "method"]
    parent_claim_id: int | None = None

    @model_validator(mode="after")
    def validate_dependency(self):
        if self.claim_dependency_type == "dependent" and self.parent_claim_id is None:
            raise ValueError("parent_claim_id is required for dependent claims")
        if self.claim_dependency_type == "independent" and self.parent_claim_id is not None:
            raise ValueError("parent_claim_id must be null for independent claims")
        return self


class ClaimTextUpdate(BaseModel):
    claim_text: str


# ── Response schemas ────────────────────────────────────────────

class ClaimResponse(BaseModel):
    claim_id: int
    patent_id: int
    claim_number: int
    claim_dependency_type: Literal["independent", "dependent"]
    claim_category: Literal["apparatus", "method"]
    parent_claim_id: int | None
    claim_text: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
