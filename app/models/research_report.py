from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ResearchReport(Base):
    __tablename__ = "research_report"

    research_report_id: Mapped[int] = mapped_column(primary_key=True)
    patent_id: Mapped[int] = mapped_column(ForeignKey("patent.patent_id"), unique=True)
    executive_summary: Mapped[str | None] = mapped_column(Text, default=None)
    search_strategy: Mapped[str | None] = mapped_column(Text, default=None)
    classification_and_keywords: Mapped[str | None] = mapped_column(Text, default=None)
    element_patent_analysis: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    patent: Mapped["Patent"] = relationship(back_populates="research_report")
    documents: Mapped[list["ResearchReportDocument"]] = relationship(
        back_populates="research_report",
        cascade="all, delete-orphan",
        order_by="ResearchReportDocument.created_at.desc()",
    )


class ResearchReportDocument(Base):
    __tablename__ = "research_report_document"

    document_id: Mapped[int] = mapped_column(primary_key=True)
    research_report_id: Mapped[int] = mapped_column(
        ForeignKey("research_report.research_report_id", ondelete="CASCADE")
    )
    original_filename: Mapped[str] = mapped_column(String(512))
    stored_filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str | None] = mapped_column(String(255), default=None)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    research_report: Mapped["ResearchReport"] = relationship(back_populates="documents")
