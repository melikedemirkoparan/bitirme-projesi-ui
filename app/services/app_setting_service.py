"""Read/write helpers for the `app_setting` key/value table.

Used for app-level singletons that must survive restarts (the LLM
endpoint URL is the first user). Per-patent or per-claim data should
not live here — it has dedicated tables.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.app_setting import AppSetting


def get_value(db: Session, key: str) -> str | None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else None


def set_value(db: Session, key: str, value: str | None) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()


def get_value_standalone(key: str) -> str | None:
    """Convenience wrapper that opens its own short-lived session.

    Use this from non-request code paths (startup hooks, modules that
    do not have a Session injected). For request handlers, prefer
    `get_value(db, key)` with the request-scoped session.
    """
    db = SessionLocal()
    try:
        return get_value(db, key)
    finally:
        db.close()


def set_value_standalone(key: str, value: str | None) -> None:
    db = SessionLocal()
    try:
        set_value(db, key, value)
    finally:
        db.close()
