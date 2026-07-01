import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import health, vault as vault_api
from .config import settings
from .db.database import init_db
from .kafka.admin import ensure_topics
from .logging_conf import setup_logging
from .providers.factory import active_provider_name
from .vault.registry import VaultValidationError, register_vault

log = setup_logging("api")


def _auto_register_sample_vault() -> None:
    if not settings.auto_register_sample_vault:
        return
    path = os.path.join(settings.vault_root, settings.default_vault_name)
    candidate = path if os.path.isdir(path) else settings.vault_root
    try:
        vid, status, _ = register_vault(
            settings.default_vault_name, candidate, settings.default_user_id,
            vault_id=settings.default_vault_id,
        )
        log.info("sample vault %s -> %s (%s)", candidate, status, vid)
    except VaultValidationError as e:
        log.warning("sample vault auto-register skipped: %s", e)


def _startup() -> None:
    log.info("starting API (ai_provider=%s)", active_provider_name())
    init_db()
    ensure_topics()
    _auto_register_sample_vault()
    log.info("API startup complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _startup()
    yield


app = FastAPI(title="ElasticGPT RAG Platform", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(vault_api.router)


@app.get("/")
def root() -> dict:
    return {"service": "elasticgpt-rag", "provider": active_provider_name()}
