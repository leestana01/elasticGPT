"""Event schemas for the ingestion pipeline (US-03-01).

Versioning strategy: every event carries ``schema_version`` (currently
``SCHEMA_VERSION``). Additive fields keep the same version; a breaking change
bumps the version and consumers branch on it. Downstream events carry
``source_event_id`` so a chunk can be traced back to the file-change that
produced it. Models allow extra fields so producers can enrich payloads without
breaking older consumers.
"""
from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = 1


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")


class FileChangedEvent(_Base):
    event_id: str
    event_type: str  # FILE_CREATED | FILE_UPDATED | FILE_DELETED | FILE_RENAMED
    vault_id: str
    path: str
    schema_version: int = SCHEMA_VERSION
    user_id: str | None = None
    old_path: str | None = None
    file_type: str | None = "markdown"
    content_hash: str | None = None


class Chunk(_Base):
    chunk_id: str
    chunk_index: int
    heading_path: str
    content: str
    content_for_embedding: str
    chunk_hash: str
    content_vector: list[float] | None = None
    embedding_model: str | None = None


class NoteParsedEvent(_Base):
    event_id: str
    source_event_id: str
    schema_version: int = SCHEMA_VERSION
    note_id: str
    vault_id: str
    user_id: str | None = None
    path: str
    title: str
    folder: str
    tags: list[str] = []
    outgoing_links: list[str] = []
    frontmatter: dict = {}
    source_type: str = "original"
    note_version: int
    content_hash: str
    sections: list[dict] = []


class NoteChunkedEvent(_Base):
    event_id: str
    source_event_id: str
    schema_version: int = SCHEMA_VERSION
    note_id: str
    vault_id: str
    user_id: str | None = None
    path: str
    title: str
    folder: str
    tags: list[str] = []
    outgoing_links: list[str] = []
    source_type: str = "original"
    note_version: int
    content_hash: str
    chunks: list[Chunk] = []


class ChunkEmbeddedEvent(NoteChunkedEvent):
    """Same shape as NoteChunkedEvent, but each chunk now has content_vector."""
