import logging
import time
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..config import settings

log = logging.getLogger("db")

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def wait_for_db(retries: int = 20, delay: float = 2.0) -> None:
    for attempt in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception:  # noqa: BLE001
            log.warning("postgres not ready, retry %d", attempt + 1)
            time.sleep(delay)
    raise RuntimeError("could not connect to postgres")


def init_db() -> None:
    from . import models  # noqa: F401  (registers mappers)

    wait_for_db()
    Base.metadata.create_all(engine)
    log.info("database initialized")


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
