from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import chat, health, retrieval, vault as vault_api
from .db.database import init_db
from .es.indices import bootstrap_indices
from .kafka.admin import ensure_topics
from .logging_conf import setup_logging
from .providers.factory import active_provider_name
from .vault.registry import ensure_sample_vault

log = setup_logging("api")


def _startup() -> None:
    log.info("starting API (ai_provider=%s)", active_provider_name())
    init_db()
    ensure_topics()
    bootstrap_indices()
    ensure_sample_vault()
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
app.include_router(chat.router)
app.include_router(retrieval.router)


@app.get("/")
def root() -> dict:
    return {"service": "elasticgpt-rag", "provider": active_provider_name()}
