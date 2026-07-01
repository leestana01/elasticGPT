import datetime
import os
import re

import frontmatter

FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# Obsidian inline tag: '#' immediately followed by a tag char (so '# Heading' is not a tag)
TAG_RE = re.compile(r"(?<![\w/#])#([A-Za-z0-9_/가-힣][A-Za-z0-9_/가-힣-]*)")
WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]]+)\]\]")
EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    return obj


def _strip_code(text: str) -> str:
    return INLINE_CODE_RE.sub(" ", FENCE_RE.sub(" ", text))


def _build_sections(body: str, default_title: str) -> list[dict]:
    sections: list[dict] = []
    stack: list[tuple[int, str]] = []
    cur_lines: list[str] = []
    cur_path = default_title

    def flush():
        text = "\n".join(cur_lines).strip()
        if text:
            sections.append({"heading_path": cur_path, "text": text})

    for line in body.split("\n"):
        m = HEADING_RE.match(line)
        if m:
            flush()
            cur_lines = []
            level = len(m.group(1))
            htext = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, htext))
            cur_path = " > ".join(t for _, t in stack)
        else:
            cur_lines.append(line)
    flush()
    return sections


def parse_markdown(raw: str, path: str) -> dict:
    post = frontmatter.loads(raw)
    meta = post.metadata or {}
    body = post.content or ""

    title = meta.get("title")
    if not title:
        m = re.search(r"^#\s+(.*)$", body, re.M)
        title = m.group(1).strip() if m else os.path.splitext(os.path.basename(path))[0]

    text_wo_code = _strip_code(body)

    fm_tags = meta.get("tags") or []
    if isinstance(fm_tags, str):
        fm_tags = [t for t in re.split(r"[,\s]+", fm_tags) if t]
    tags = sorted({str(t).lstrip("#") for t in fm_tags} | set(TAG_RE.findall(text_wo_code)))

    outgoing_links = sorted(
        {m.split("|")[0].split("#")[0].strip() for m in WIKILINK_RE.findall(text_wo_code) if m.strip()}
    )
    attachments = sorted(set(EMBED_RE.findall(text_wo_code) + IMG_RE.findall(text_wo_code)))
    headings = []
    for line in body.split("\n"):
        hm = HEADING_RE.match(line)
        if hm:
            headings.append({"level": len(hm.group(1)), "text": hm.group(2).strip()})

    return {
        "title": str(title),
        "frontmatter": _jsonable(meta),
        "tags": tags,
        "outgoing_links": outgoing_links,
        "attachments": attachments,
        "headings": headings,
        "code_blocks": FENCE_RE.findall(raw),
        "sections": _build_sections(body, str(title)),
        "plain_text": text_wo_code.strip(),
    }
