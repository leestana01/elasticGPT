from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Vault(Base):
    __tablename__ = "vaults"

    vault_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1024), unique=True)
    user_id: Mapped[str] = mapped_column(String(64), default="user_001")
    status: Mapped[str] = mapped_column(String(32), default="REGISTERED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
