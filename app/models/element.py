from __future__ import annotations
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Element(Base):
    __tablename__ = "element"

    element_id: Mapped[int] = mapped_column(primary_key=True)
    patent_id: Mapped[int] = mapped_column(ForeignKey("patent.patent_id"))
    element_name: Mapped[str] = mapped_column(String(255))
    reference_number: Mapped[str] = mapped_column(String(10), nullable=False)
    definition_text: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    patent: Mapped["Patent"] = relationship(back_populates="elements")
    claim_elements: Mapped[list["ClaimElement"]] = relationship(back_populates="element", cascade="all, delete-orphan")
