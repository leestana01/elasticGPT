import logging

from ..config import settings
from ..db.database import session_scope
from ..db.models import GoldenItem
from ..events.ids import new_id

log = logging.getLogger("eval.golden")

DEFAULT_GOLDEN = [
    {
        "question": "Kafka 기반 RAG 설계에서 DLQ는 어떻게 처리하나요?",
        "expected_note_paths": ["30_Reference/Dead Letter Queue.md", "10_Project/RAG 시스템 설계.md"],
        "must_cite": ["30_Reference/Dead Letter Queue.md"],
    },
    {
        "question": "Hybrid Search는 어떤 방식으로 동작하나요?",
        "expected_note_paths": ["30_Reference/Hybrid Search.md"],
        "must_cite": ["30_Reference/Hybrid Search.md"],
    },
    {
        "question": "Elasticsearch에서 dense_vector kNN 검색은 어떻게 하나요?",
        "expected_note_paths": ["20_Area/Elasticsearch.md"],
        "must_cite": ["20_Area/Elasticsearch.md"],
    },
    {
        "question": "Obsidian 자동 갱신 전략의 핵심은 무엇인가요?",
        "expected_note_paths": ["10_Project/Obsidian 자동 갱신 전략.md"],
        "must_cite": ["10_Project/Obsidian 자동 갱신 전략.md"],
    },
    {
        "question": "Kafka consumer group과 offset의 역할은 무엇인가요?",
        "expected_note_paths": ["20_Area/Kafka.md"],
        "must_cite": ["20_Area/Kafka.md"],
    },
    {
        "question": "2026년 프로야구 한국시리즈 우승팀은 어디인가요?",
        "expected_note_paths": [],
        "must_cite": [],
        "should_abstain": True,
    },
]


def _to_dict(g: GoldenItem) -> dict:
    return {
        "itemId": g.item_id,
        "vaultId": g.vault_id,
        "question": g.question,
        "expected_note_paths": g.expected_note_paths or [],
        "expected_chunk_ids": g.expected_chunk_ids or [],
        "expectedAnswer": g.expected_answer,
        "must_cite": g.must_cite or [],
        "should_abstain": g.should_abstain,
    }


def register_item(vault_id: str, data: dict) -> dict:
    with session_scope() as session:
        item = GoldenItem(
            item_id=new_id("gold"),
            vault_id=vault_id,
            question=data["question"],
            expected_note_paths=data.get("expected_note_paths", []),
            expected_chunk_ids=data.get("expected_chunk_ids", []),
            expected_answer=data.get("expected_answer"),
            must_cite=data.get("must_cite", []),
            should_abstain=data.get("should_abstain", False),
        )
        session.add(item)
        session.flush()
        return _to_dict(item)


def list_items(vault_id: str) -> list[dict]:
    with session_scope() as session:
        return [_to_dict(g) for g in session.query(GoldenItem).filter(GoldenItem.vault_id == vault_id).all()]


def ensure_default_golden_set() -> None:
    vault_id = settings.default_vault_id
    with session_scope() as session:
        exists = session.query(GoldenItem).filter(GoldenItem.vault_id == vault_id).first()
        if exists:
            return
    for data in DEFAULT_GOLDEN:
        register_item(vault_id, data)
    log.info("seeded %d default golden items", len(DEFAULT_GOLDEN))
