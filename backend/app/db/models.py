from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
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


class NoteUpdateCandidate(Base):
    __tablename__ = "note_update_candidates"

    candidate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    answer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vault_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_type: Mapped[str] = mapped_column(String(16))  # NEW | APPEND
    target_note_path: Mapped[str] = mapped_column(String(1024))
    target_heading: Mapped[str | None] = mapped_column(String(512), nullable=True)
    markdown_patch: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    source_question: Mapped[str] = mapped_column(Text, default="")
    source_answer: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list] = mapped_column(JSON, default=list)
    related_notes: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    patch_hash: Mapped[str] = mapped_column(String(80), index=True)
    origin: Mapped[str] = mapped_column(String(16), default="knowledge")  # knowledge | correction
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DlqEvent(Base):
    __tablename__ = "dlq_events"

    dlq_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_topic: Mapped[str] = mapped_column(String(128), index=True)
    consumer_group: Mapped[str] = mapped_column(String(128))
    error_type: Mapped[str] = mapped_column(String(128))
    error_message: Mapped[str] = mapped_column(Text, default="")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="NEW", index=True)  # NEW | REPROCESSED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReindexJob(Base):
    __tablename__ = "reindex_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vault_id: Mapped[str] = mapped_column(String(64), index=True)
    path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="RUNNING")  # RUNNING | COMPLETED | FAILED
    note_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Feedback(Base):
    __tablename__ = "feedbacks"

    feedback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    answer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vault_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vote: Mapped[str | None] = mapped_column(String(8), nullable=True)  # up | down
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
