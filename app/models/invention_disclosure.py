from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InventionDisclosure(Base):
    __tablename__ = "invention_disclosure"

    idf_id: Mapped[int] = mapped_column(primary_key=True)
    patent_id: Mapped[int] = mapped_column(ForeignKey("patent.patent_id"), unique=True)
    prior_art_and_problems: Mapped[str | None] = mapped_column(Text, default=None)
    closest_prior_patents: Mapped[str | None] = mapped_column(Text, default=None)
    novel_features: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    patent: Mapped["Patent"] = relationship(back_populates="invention_disclosure")
