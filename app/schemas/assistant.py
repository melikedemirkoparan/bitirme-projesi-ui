from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AssistantRequest(BaseModel):
    pattern_id: Literal["P1", "P2", "P3"]
    term: str | None = None  # required only for P3


class EvidenceCard(BaseModel):
    evidence_id: str
    document_type: str
    field: str
    excerpt: str
    match_term: str | None = None
    usefulness_note: str | None = None


class IndependentCandidate(BaseModel):
    label: str
    features: list[str]
    reason: str
    support_level: Literal["explicit", "inferred"] | None = None
    support_note: str | None = None


class DependentCandidate(BaseModel):
    label: str
    depends_on: str
    features: list[str]
    reason: str
    support_level: Literal["explicit", "inferred"] | None = None
    support_note: str | None = None


class ClaimStructure(BaseModel):
    independent_candidates: list[IndependentCandidate]
    dependent_candidates: list[DependentCandidate]
    cautions: list[str]


class AssistantResponse(BaseModel):
    pattern_id: str
    title: str
    support_level: Literal["explicit", "inferred", "insufficient"]
    answer: str
    insufficient_message: str
    claim_structure: ClaimStructure | None = None
    evidence: list[EvidenceCard]
