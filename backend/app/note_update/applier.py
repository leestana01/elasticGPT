import logging
import os
import re

from ..vault.registry import get_vault_path
from .markdown import APPEND_HEADING

log = logging.getLogger("note_update.applier")


def _safe_new_path(vault_path: str, rel_path: str) -> tuple[str, str]:
    abs_path = os.path.join(vault_path, rel_path)
    if not os.path.exists(abs_path):
        return abs_path, rel_path
    base, ext = os.path.splitext(abs_path)
    i = 1
    while os.path.exists(f"{base} ({i}){ext}"):
        i += 1
    new_abs = f"{base} ({i}){ext}"
    return new_abs, os.path.relpath(new_abs, vault_path)


def _insert_under_heading(content: str, heading: str, block: str) -> str:
    lines = content.split("\n")
    marker = f"## {heading}"
    for i, line in enumerate(lines):
        if line.strip() == marker:
            j = i + 1
            while j < len(lines) and not re.match(r"^#{1,2}\s", lines[j]):
                j += 1
            return "\n".join(lines[:j] + [block.rstrip(), ""] + lines[j:])
    return content.rstrip() + f"\n\n{marker}\n{block.rstrip()}\n"


def apply_candidate(candidate: dict) -> dict:
    """Apply an approved candidate to the vault filesystem.

    NEW  -> create a markdown file (collision-safe suffix).
    APPEND -> insert the block under the target heading, creating it if missing,
    without deleting existing content, snapshotting for rollback.
    """
    vault_path = get_vault_path(candidate["vaultId"])
    if not vault_path:
        raise ValueError(f"unknown vault {candidate['vaultId']}")

    rel = candidate["targetNotePath"]
    patch = candidate["markdownPatch"]

    if candidate["candidateType"] == "NEW":
        abs_path, rel = _safe_new_path(vault_path, rel)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(patch)
        log.info("created note %s", rel)
        return {"path": rel, "action": "created"}

    heading = candidate.get("targetHeading") or APPEND_HEADING
    abs_path = os.path.join(vault_path, rel)

    if not os.path.exists(abs_path):
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        title = os.path.splitext(os.path.basename(rel))[0]
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n## {heading}\n{patch.rstrip()}\n")
        log.info("created missing target %s", rel)
        return {"path": rel, "action": "created-missing"}

    with open(abs_path, encoding="utf-8") as f:
        original = f.read()
    if patch.strip() and patch.strip() in original:
        log.info("patch already present, skipping %s", rel)
        return {"path": rel, "action": "skipped-duplicate"}

    try:
        new_content = _insert_under_heading(original, heading, patch)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception:
        with open(abs_path, "w", encoding="utf-8") as f:  # rollback
            f.write(original)
        raise
    log.info("appended to %s under '%s'", rel, heading)
    return {"path": rel, "action": "appended"}
