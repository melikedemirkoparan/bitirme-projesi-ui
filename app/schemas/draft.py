"""Schemas for the Patent Draft Composer.

Spec: docs/patent_draft_composer.md

The composer returns a patent file with three parts, in this order:
  1. Description -- LLM-written, English
  2. Claims      -- deterministic, copied verbatim from the saved claims
  3. Abstract    -- LLM-written, English, summarises the Description

Each part is one ``DraftSection``; ``sections`` therefore holds three
items. The shape is intentionally section-agnostic so the part list can
evolve without a schema change.
"""

from pydantic import BaseModel


class DraftGenerateRequest(BaseModel):
    # Optional claims text shown/edited in the composer textarea. When
    # omitted or empty the service falls back to the project's saved claims.
    claims_text: str | None = None


class DraftSection(BaseModel):
    number: int                # 1=Description, 2=Claims, 3=Abstract
    key: str                   # "description" | "claims" | "abstract"
    title: str                 # "Description" | "Claims" | "Abstract"
    body: str
    # True when the section text came from the LLM (or is the deterministic
    # claims section); False when it is a "could not generate" placeholder.
    generated: bool


class DraftGenerateResponse(BaseModel):
    patent_id: int
    backend: str               # "remote" (Colab) | "local" (Ollama)
    sections: list[DraftSection]
    draft_html: str            # ready-to-render HTML, also persisted as patent_draft
    warnings: list[str]        # per-section problems, if any
