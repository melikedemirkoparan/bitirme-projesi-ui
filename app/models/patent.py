from datetime import datetime

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Patent(Base):
    __tablename__ = "patent"

    patent_id: Mapped[int] = mapped_column(primary_key=True)
    patent_name: Mapped[str] = mapped_column(String(255))
    patent_owner: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str | None] = mapped_column(String(255), default=None)
    invention_context: Mapped[str | None] = mapped_column(Text, default=None)
    patent_draft: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # One-to-one (may be absent initially)
    invention_disclosure: Mapped["InventionDisclosure | None"] = relationship(
        back_populates="patent", uselist=False, cascade="all, delete-orphan"
    )
    research_report: Mapped["ResearchReport | None"] = relationship(
        back_populates="patent", uselist=False, cascade="all, delete-orphan"
    )
    inventor_qa: Mapped["InventorQA | None"] = relationship(
        back_populates="patent", uselist=False, cascade="all, delete-orphan"
    )

    # One-to-many
    claims: Mapped[list["Claim"]] = relationship(
        back_populates="patent", cascade="all, delete-orphan"
    )
    elements: Mapped[list["Element"]] = relationship(
        back_populates="patent", cascade="all, delete-orphan"
    )
