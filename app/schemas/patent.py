from datetime import datetime

from pydantic import BaseModel


# ── Nested document schemas (optional during project creation) ──

class InventionDisclosureCreate(BaseModel):
    prior_art_and_problems: str | None = None
    closest_prior_patents: str | None = None
    novel_features: str | None = None


class ResearchReportCreate(BaseModel):
    executive_summary: str | None = None
    search_strategy: str | None = None
    classification_and_keywords: str | None = None
    element_patent_analysis: str | None = None


class InventorQACreate(BaseModel):
    questions_and_answers: str | None = None


# ── Patent creation request ─────────────────────────────────────
# Follows the suggested payload shape from docs/home_page.md:
# patent_name + patent_owner are required,
# document sections are optional nested objects.

class PatentCreate(BaseModel):
    patent_name: str
    patent_owner: str
    invention_disclosure: InventionDisclosureCreate | None = None
    research_report: ResearchReportCreate | None = None
    inventor_qna: InventorQACreate | None = None


class PatentUpdate(BaseModel):
    patent_name: str | None = None
    patent_owner: str | None = None


# ── Response schemas ────────────────────────────────────────────

class PatentSummary(BaseModel):
    patent_id: int
    patent_name: str
    patent_owner: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PatentDetail(BaseModel):
    patent_id: int
    patent_name: str
    patent_owner: str
    patent_draft: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
