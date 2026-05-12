"""Generic key/value store for app-level configuration that must
survive server restarts.

Keep this table tiny — it is intended for a handful of singletons
(LLM endpoint URL, future feature flags, etc.) and not for
per-patent or per-claim data, which lives in dedicated tables.
"""

from datetime import datetime

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSetting(Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, default=None)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
