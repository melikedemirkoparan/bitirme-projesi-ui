from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
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
