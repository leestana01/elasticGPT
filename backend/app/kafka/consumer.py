import json
import logging
import time

from kafka import KafkaConsumer

from ..config import settings
from ..events.ids import new_id, now_iso
from . import topics as T
from .producer import publish

log = logging.getLogger("kafka.consumer")


class PermanentError(Exception):
    """Raised by handlers for non-retryable failures (validation etc.).

    These bypass retries and go straight to the dead-letter queue (US-09-01).
    """


def _touch_heartbeat() -> None:
    try:
        with open(settings.heartbeat_file, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass


def _to_dlq(source_topic: str, group: str, event, error: Exception, retry_count: int) -> None:
    dlq_event = {
        "event_id": new_id("dlq"),
        "schema_version": 1,
        "source_topic": source_topic,
        "consumer_group": group,
        "error_type": type(error).__name__,
        "error_message": str(error)[:2000],
        "retry_count": retry_count,
        "failed_at": now_iso(),
        "payload": event,
    }
    try:
        key = event.get("event_id") if isinstance(event, dict) else None
        publish(T.DEAD_LETTER, dlq_event, key=key)
        log.error("→ DLQ topic=%s group=%s error=%s: %s", source_topic, group, type(error).__name__, error)
    except Exception:  # noqa: BLE001
        log.exception("failed to publish to DLQ")


def _process(source_topic: str, group: str, handler, event) -> None:
    attempt = 0
    while True:
        try:
            handler(event)
            return
        except PermanentError as e:
            _to_dlq(source_topic, group, event, e, attempt)
            return
        except Exception as e:  # noqa: BLE001 - transient, apply local retry + backoff
            attempt += 1
            if attempt > settings.max_local_retries:
                _to_dlq(source_topic, group, event, e, attempt - 1)
                return
            backoff = settings.retry_backoff_base * (2 ** (attempt - 1))
            log.warning(
                "handler error (attempt %d/%d) topic=%s: %s; retry in %.1fs",
                attempt, settings.max_local_retries, source_topic, e, backoff,
            )
            time.sleep(backoff)


def run_consumer(topic_list, group: str, handler) -> None:
    """Long-running poll loop with heartbeat, local retry and DLQ."""
    if isinstance(topic_list, str):
        topic_list = [topic_list]
    consumer = KafkaConsumer(
        *topic_list,
        bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
        group_id=f"{settings.consumer_group_prefix}.{group}",
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    log.info("consumer up: topics=%s group=%s", topic_list, group)
    _touch_heartbeat()
    while True:
        _touch_heartbeat()
        records = consumer.poll(timeout_ms=1000, max_records=50)
        for tp, messages in records.items():
            for message in messages:
                _process(tp.topic, group, handler, message.value)
        _touch_heartbeat()
