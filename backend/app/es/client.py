import logging

from elasticsearch import Elasticsearch

from ..config import settings

log = logging.getLogger("es.client")

_client: Elasticsearch | None = None


def get_es() -> Elasticsearch:
    global _client
    if _client is None:
        _client = Elasticsearch(
            settings.elasticsearch_url,
            request_timeout=30,
            retry_on_timeout=True,
            max_retries=3,
        )
    return _client


def ping() -> bool:
    try:
        return bool(get_es().ping())
    except Exception:  # noqa: BLE001
        return False
