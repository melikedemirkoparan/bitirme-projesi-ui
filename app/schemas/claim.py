from __future__ import annotations
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


# ── Create request ──────────────────────────────────────────────
# Collects the fields from the Add Claim modal (docs/claim_workspace.md).
# claim_number is assigned by the service, not the client.

class ClaimCreate(BaseModel):
    claim_dependency_type: Literal["independent", "dependent"]
    claim_category: Literal["apparatus", "method"]
    parent_claim_ids: list[int] = []

    @model_validator(mode="after")
    def validate_dependency(self):
        if self.claim_dependency_type == "dependent" and not self.parent_claim_ids:
            raise ValueError("parent_claim_ids is required for dependent claims")
        if self.claim_dependency_type == "independent" and self.parent_claim_ids:
            raise ValueError("parent_claim_ids must be empty for independent claims")
        return self


class ClaimTextUpdate(BaseModel):
    claim_text: str


class ClaimUpdate(BaseModel):
    claim_dependency_type: str | None = None
    claim_category: str | None = None
    parent_claim_ids: list[int] | None = None


# ── Claim draft generation ──────────────────────────────────────

class ClaimDraftRequest(BaseModel):
    """
    system_name:
        The main claimed subject for the preamble.
        e.g. 'an adjustable equipment mounting system (1)'

    group_b_element_ids:
        Independent apparatus only. Element IDs that contribute to
        inventive step → 'characterized in that' portion (Group B).
        Remaining linked elements become Group A → 'comprising'.
        Ignored for dependent / method claims.

    parent_claim_numbers:
        Dependent claims only. The claim number(s) this claim references.
        - one number  → 'according to claim X'
        - two or more → 'according to any one of claims X, Y, ...'
        If empty the service falls back to the stored parent_claim_id.

    method_purpose:
        Independent method claims only. Fills the
        'A method for <purpose/field>' slot.
        e.g. 'mounting equipment on a body'
        If omitted, system_name is used as fallback.
    """
    system_name: str = ""
    group_b_element_ids: list[int] = []
    parent_claim_numbers: list[int] = []
    method_purpose: str = ""


class ClaimDraftResult(BaseModel):
    claim_id: int
    claim_number: int
    claim_dependency_type: str
    claim_category: str
    success: bool
    claim_text: str | None = None
    warning: str | None = None


# ── Response schemas ────────────────────────────────────────────

class ClaimResponse(BaseModel):
    claim_id: int
    patent_id: int
    claim_number: int
    claim_dependency_type: Literal["independent", "dependent"]
    claim_category: Literal["apparatus", "method"]
    parent_claim_ids: list[int]
    claim_text: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
