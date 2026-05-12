from datetime import datetime

from pydantic import BaseModel


class ResearchReportDocumentRead(BaseModel):
    document_id: int
    original_filename: str
    mime_type: str | None = None
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ResearchReportRead(BaseModel):
    research_report_id: int
    patent_id: int
    executive_summary: str | None = None
    search_strategy: str | None = None
    classification_and_keywords: str | None = None
    element_patent_analysis: str | None = None
    created_at: datetime
    updated_at: datetime
    documents: list[ResearchReportDocumentRead] = []

    model_config = {"from_attributes": True}


class ResearchReportUpdate(BaseModel):
    executive_summary: str | None = None
    search_strategy: str | None = None
    classification_and_keywords: str | None = None
    element_patent_analysis: str | None = None
