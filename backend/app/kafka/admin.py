import logging
import time

from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import NoBrokersAvailable, TopicAlreadyExistsError

from ..config import settings
from . import topics as T

log = logging.getLogger("kafka.admin")


def ensure_topics(partitions: int = 1, replication: int = 1) -> None:
    """Create every platform topic if missing. Safe to call repeatedly."""
    admin = None
    for attempt in range(15):
        try:
            admin = KafkaAdminClient(
                bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
                client_id="elasticgpt-admin",
            )
            break
        except NoBrokersAvailable:
            log.warning("kafka not ready (admin), retry %d", attempt + 1)
            time.sleep(2)
    if admin is None:
        raise RuntimeError("could not connect to kafka admin")

    for name in T.ALL_TOPICS:
        try:
            admin.create_topics([NewTopic(name=name, num_partitions=partitions, replication_factor=replication)])
            log.info("created topic %s", name)
        except TopicAlreadyExistsError:
            pass
        except Exception as e:  # noqa: BLE001 - tolerate races / already-exists variants
            log.info("topic %s not created (%s)", name, type(e).__name__)
    admin.close()
