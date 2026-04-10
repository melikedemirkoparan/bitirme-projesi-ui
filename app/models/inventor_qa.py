from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
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
