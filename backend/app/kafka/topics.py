# Kafka topic names for the whole platform. Kept in one place so producers and
# consumers reference identical strings (US-03-01).

# ---- Ingestion pipeline ----
FILE_CHANGED = "obsidian.file.changed"
NOTE_PARSED = "obsidian.note.parsed"
NOTE_CHUNKED = "obsidian.note.chunked"
CHUNK_EMBEDDED = "obsidian.chunk.embedded"
CHUNK_INDEXED = "obsidian.chunk.indexed"
NOTE_DELETED = "obsidian.note.deleted"
REINDEX_REQUESTED = "obsidian.reindex.requested"
REINDEX_COMPLETED = "obsidian.reindex.completed"

# ---- RAG / knowledge loop ----
QUERY_ASKED = "rag.query.asked"
ANSWER_GENERATED = "rag.answer.generated"
KNOWLEDGE_EXTRACTED = "rag.knowledge.extracted"
NOTE_UPDATE_REQUESTED = "obsidian.note.update.requested"
NOTE_UPDATE_APPROVED = "obsidian.note.update.approved"
NOTE_UPDATE_REJECTED = "obsidian.note.update.rejected"
NOTE_UPDATED = "obsidian.note.updated"
FEEDBACK_CREATED = "rag.feedback.created"

# ---- Reliability ----
DEAD_LETTER = "rag.dead-letter"

ALL_TOPICS = [
    FILE_CHANGED,
    NOTE_PARSED,
    NOTE_CHUNKED,
    CHUNK_EMBEDDED,
    CHUNK_INDEXED,
    NOTE_DELETED,
    REINDEX_REQUESTED,
    REINDEX_COMPLETED,
    QUERY_ASKED,
    ANSWER_GENERATED,
    KNOWLEDGE_EXTRACTED,
    NOTE_UPDATE_REQUESTED,
    NOTE_UPDATE_APPROVED,
    NOTE_UPDATE_REJECTED,
    NOTE_UPDATED,
    FEEDBACK_CREATED,
    DEAD_LETTER,
]
