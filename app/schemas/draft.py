"""Schemas for the Patent Draft Composer.

Spec: docs/patent_draft_composer.md
"""

from pydantic import BaseModel


class DraftGenerateRequest(BaseModel):
    # Optional claims text shown/edited in the composer textarea. When
    # omitted or empty the service falls back to the project's saved claims.
    claims_text: str | None = None


class DraftSection(BaseModel):
    number: int
    key: str
    title: str
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
