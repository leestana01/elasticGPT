from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..vault.registry import VaultValidationError, get_vault, list_vaults, register_vault

router = APIRouter(prefix="/api/vaults", tags=["vault"])


class VaultRegisterRequest(BaseModel):
    name: str
    path: str
    userId: str | None = None


@router.get("")
def api_list_vaults() -> dict:
    return {"vaults": list_vaults()}


@router.post("")
def api_register_vault(req: VaultRegisterRequest) -> dict:
    try:
        vault_id, status, vault = register_vault(req.name, req.path, req.userId)
    except VaultValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"status": status, "vault": vault}


@router.get("/{vault_id}")
def api_get_vault(vault_id: str) -> dict:
    vault = get_vault(vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")
    return {"vault": vault}
