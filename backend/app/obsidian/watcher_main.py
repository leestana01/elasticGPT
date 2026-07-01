import time

from app.config import settings
from app.db.database import init_db
from app.logging_conf import setup_logging
from app.obsidian.watcher import initial_scan, start_watching
from app.vault.registry import ensure_sample_vault, list_vaults


def _touch_heartbeat() -> None:
    try:
        with open(settings.heartbeat_file, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass


def main() -> None:
    log = setup_logging("vault-watcher")
    init_db()
    ensure_sample_vault()

    vaults = list_vaults()
    log.info("starting watcher for %d vault(s)", len(vaults))
    observer = start_watching(vaults)
    for vault in vaults:
        initial_scan(vault)

    _touch_heartbeat()
    try:
        while True:
            _touch_heartbeat()
            time.sleep(5)
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
