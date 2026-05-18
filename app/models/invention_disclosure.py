from __future__ import annotations
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InventionDisclosure(Base):
    __tablename__ = "invention_disclosure"

    idf_id: Mapped[int] = mapped_column(primary_key=True)
    patent_id: Mapped[int] = mapped_column(ForeignKey("patent.patent_id"), unique=True)
    prior_art_and_problems: Mapped[str | None] = mapped_column(Text, default=None)
    closest_prior_patents: Mapped[str | None] = mapped_column(Text, default=None)
    novel_features: Mapped[str | None] = mapped_column(Text, default=None)
    bbf_text: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    patent: Mapped["Patent"] = relationship(back_populates="invention_disclosure")
    documents: Mapped[list["InventionDisclosureDocument"]] = relationship(
        back_populates="invention_disclosure",
        cascade="all, delete-orphan",
        order_by="InventionDisclosureDocument.created_at.desc()",
    )


class InventionDisclosureDocument(Base):
    __tablename__ = "invention_disclosure_document"

    document_id: Mapped[int] = mapped_column(primary_key=True)
    idf_id: Mapped[int] = mapped_column(
        ForeignKey("invention_disclosure.idf_id", ondelete="CASCADE")
    )
    original_filename: Mapped[str] = mapped_column(String(512))
    stored_filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str | None] = mapped_column(String(255), default=None)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    invention_disclosure: Mapped["InventionDisclosure"] = relationship(back_populates="documents")
