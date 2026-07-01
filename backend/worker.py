import os

from app.config import settings
from app.kafka.consumer import run_consumer
from app.logging_conf import setup_logging
from app.workers.registry import build_registry


def main() -> None:
    worker_type = os.getenv("WORKER_TYPE", settings.worker_type)
    log = setup_logging(f"worker:{worker_type}")

    registry = build_registry()
    spec = registry.get(worker_type)
    if spec is None:
        log.error("unknown WORKER_TYPE=%s (valid: %s)", worker_type, list(registry))
        raise SystemExit(1)

    log.info("starting worker type=%s topics=%s", worker_type, spec["topics"])
    run_consumer(spec["topics"], spec["group"], spec["handler"])


if __name__ == "__main__":
    main()
