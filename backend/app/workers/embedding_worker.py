import json
import logging

from ..cache.redis_client import get_redis
from ..events.build import downstream_event, pick_meta
from ..kafka import topics as T
from ..kafka.consumer import PermanentError
from ..kafka.producer import publish
from ..ops.metrics import incr, record_stage
from ..providers.factory import get_embedding_provider

log = logging.getLogger("worker.embedding")


def handle_note_chunked(event: dict) -> None:
    chunks = event.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise PermanentError("note.chunked event has no chunks")

    provider = get_embedding_provider()
    redis = get_redis()

    to_embed: list[int] = []
    texts: list[str] = []
    for i, c in enumerate(chunks):
        cache_key = f"emb:{provider.model}:{c['chunk_hash']}"
        cached = redis.get(cache_key) if redis is not None else None
        if cached:
            c["content_vector"] = json.loads(cached)
        else:
            to_embed.append(i)
            texts.append(c["content_for_embedding"])

    if texts:
        # provider.embed may raise on transient/rate-limit errors → the consumer
        # retries with exponential backoff before falling through to the DLQ.
        vectors = provider.embed(texts)
        incr("embedding_calls")
        if len(vectors) != len(texts):
            raise PermanentError("embedding count mismatch")
        for j, i in enumerate(to_embed):
            chunks[i]["content_vector"] = vectors[j]
            if redis is not None:
                redis.set(f"emb:{provider.model}:{chunks[i]['chunk_hash']}", json.dumps(vectors[j]))

    for c in chunks:
        c["embedding_model"] = provider.model

    meta = pick_meta(event)
    evt = downstream_event(event, {**meta, "chunks": chunks})
    publish(T.CHUNK_EMBEDDED, evt, key=event.get("note_id"))
    record_stage("embedded", note_id=event.get("note_id"), path=event.get("path"),
                 vault_id=event.get("vault_id"), extra={"newEmbeddings": len(texts)})
    log.info(
        "embedded %s: %d chunks (%d cached, %d new)",
        event.get("path"), len(chunks), len(chunks) - len(texts), len(texts),
    )
