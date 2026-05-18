from __future__ import annotations
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Claim(Base):
    __tablename__ = "claim"

    claim_id: Mapped[int] = mapped_column(primary_key=True)
    patent_id: Mapped[int] = mapped_column(ForeignKey("patent.patent_id"))
    claim_number: Mapped[int] = mapped_column(Integer)
    claim_dependency_type: Mapped[str] = mapped_column(String(20))  # independent | dependent
    claim_category: Mapped[str] = mapped_column(String(20))  # apparatus | method
    parent_claim_id: Mapped[int | None] = mapped_column(ForeignKey("claim.claim_id"), nullable=True)
    claim_text: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    patent: Mapped["Patent"] = relationship(back_populates="claims")
    parent_claim: Mapped["Claim | None"] = relationship(remote_side="Claim.claim_id")
    claim_elements: Mapped[list["ClaimElement"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
