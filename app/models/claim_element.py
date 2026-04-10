from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ClaimElement(Base):
    __tablename__ = "claim_element"

    claim_element_id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claim.claim_id"))
    element_id: Mapped[int] = mapped_column(ForeignKey("element.element_id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="claim_elements")
    element: Mapped["Element"] = relationship(back_populates="claim_elements")
