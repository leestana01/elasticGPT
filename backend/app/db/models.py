from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
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


class QueryLog(Base):
    __tablename__ = "query_logs"

    query_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    answer_id: Mapped[str] = mapped_column(String(64), default="")
    vault_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    retrieval_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)
    retrieval_scores: Mapped[list] = mapped_column(JSON, default=list)
    context_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    answer: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list] = mapped_column(JSON, default=list)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
