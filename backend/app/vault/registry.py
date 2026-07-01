import logging
import os

from ..config import settings
from ..db.database import session_scope
from ..db.models import Vault
from ..events.ids import new_id

log = logging.getLogger("vault.registry")


class VaultValidationError(Exception):
    """Raised when a vault cannot be registered (e.g. path missing)."""


def _to_dict(v: Vault) -> dict:
    return {
        "vaultId": v.vault_id,
        "name": v.name,
        "path": v.path,
        "userId": v.user_id,
        "status": v.status,
        "createdAt": v.created_at.isoformat() if v.created_at else None,
    }


def register_vault(name: str, path: str, user_id: str | None = None, vault_id: str | None = None):
    """Register a vault. Returns (vault_id, status, vault_dict).

    status is REGISTERED for new vaults, ALREADY_REGISTERED for duplicate paths.
    """
    user_id = user_id or settings.default_user_id
    if not os.path.isdir(path):
        raise VaultValidationError(f"vault path does not exist: {path}")

    with session_scope() as session:
        existing = session.query(Vault).filter(Vault.path == path).one_or_none()
        if existing is not None:
            return existing.vault_id, "ALREADY_REGISTERED", _to_dict(existing)
        vid = vault_id or new_id("vault")
        vault = Vault(vault_id=vid, name=name, path=path, user_id=user_id, status="REGISTERED")
        session.add(vault)
        session.flush()
        return vid, "REGISTERED", _to_dict(vault)


def ensure_sample_vault() -> dict | None:
    """Idempotently register the mounted sample vault (US-01-02).

    Used by both the API and the vault-watcher on startup so either can run first.
    """
    if not settings.auto_register_sample_vault:
        return None
    path = os.path.join(settings.vault_root, settings.default_vault_name)
    candidate = path if os.path.isdir(path) else settings.vault_root
    try:
        _, status, vault = register_vault(
            settings.default_vault_name, candidate, settings.default_user_id,
            vault_id=settings.default_vault_id,
        )
        log.info("sample vault %s -> %s (%s)", candidate, status, vault["vaultId"])
        return vault
    except VaultValidationError as e:
        log.warning("sample vault auto-register skipped: %s", e)
        return None


def list_vaults() -> list[dict]:
    with session_scope() as session:
        return [_to_dict(v) for v in session.query(Vault).order_by(Vault.created_at).all()]


def get_vault(vault_id: str) -> dict | None:
    with session_scope() as session:
        v = session.get(Vault, vault_id)
        return _to_dict(v) if v else None


def get_vault_path(vault_id: str) -> str | None:
    with session_scope() as session:
        v = session.get(Vault, vault_id)
        return v.path if v else None
