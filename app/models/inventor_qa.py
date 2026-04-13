from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InventorQA(Base):
    __tablename__ = "inventor_qa"

    qna_id: Mapped[int] = mapped_column(primary_key=True)
    patent_id: Mapped[int] = mapped_column(ForeignKey("patent.patent_id"), unique=True)
    questions_and_answers: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    patent: Mapped["Patent"] = relationship(back_populates="inventor_qa")
    documents: Mapped[list["InventorQADocument"]] = relationship(
        back_populates="inventor_qa",
        cascade="all, delete-orphan",
        order_by="InventorQADocument.created_at.desc()",
    )


class InventorQADocument(Base):
    __tablename__ = "inventor_qa_document"

    document_id: Mapped[int] = mapped_column(primary_key=True)
    qna_id: Mapped[int] = mapped_column(
        ForeignKey("inventor_qa.qna_id", ondelete="CASCADE")
    )
    original_filename: Mapped[str] = mapped_column(String(512))
    stored_filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str | None] = mapped_column(String(255), default=None)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    inventor_qa: Mapped["InventorQA"] = relationship(back_populates="documents")
