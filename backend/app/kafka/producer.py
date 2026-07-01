import json
import logging
import time

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

from ..config import settings

log = logging.getLogger("kafka.producer")

_producer: KafkaProducer | None = None


def get_producer() -> KafkaProducer:
    global _producer
    if _producer is None:
        last_err = None
        for attempt in range(10):
            try:
                _producer = KafkaProducer(
                    bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
                    value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                    acks="all",
                    retries=5,
                    linger_ms=20,
                )
                break
            except NoBrokersAvailable as e:
                last_err = e
                log.warning("kafka not ready (producer), retry %d", attempt + 1)
                time.sleep(2)
        if _producer is None:
            raise RuntimeError(f"could not connect to kafka: {last_err}")
    return _producer


def publish(topic: str, event: dict, key: str | None = None):
    producer = get_producer()
    future = producer.send(topic, value=event, key=key)
    producer.flush()
    return future
