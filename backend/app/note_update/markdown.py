import re

from ..events.ids import now_iso

APPEND_HEADING = "질의응답 메모"


def slugify(text: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣 _-]", "", text).strip()
    s = re.sub(r"\s+", " ", s)
    return (s[:maxlen] or "note").strip()


def citation_lines(citations: list[dict]) -> str:
    lines = []
    for c in citations:
        title = c.get("noteTitle") or ""
        heading = c.get("headingPath") or ""
        lines.append(f"- [[{title}]] ({heading})")
    return "\n".join(lines) if lines else "- (없음)"


def related_wikilinks(titles: list[str]) -> str:
    return " ".join(f"[[{t}]]" for t in titles if t)


def build_append_block(question: str, summary: str, citations: list[dict]) -> str:
    return (
        f"\n**Q.** {question}\n\n"
        f"**A.** {summary}\n\n"
        f"출처:\n{citation_lines(citations)}\n"
    )


def build_new_note(question: str, summary: str, answer: str, citations: list[dict], related: list[str]) -> str:
    title = slugify(question)
    return (
        "---\n"
        f"title: QA - {title}\n"
        "tags: [generated, qa]\n"
        f"created: {now_iso()[:10]}\n"
        "source: elasticgpt\n"
        "---\n\n"
        f"# QA - {title}\n\n"
        f"## 질문\n\n{question}\n\n"
        f"## 정리\n\n{summary}\n\n"
        f"## 답변 원문\n\n{answer}\n\n"
        f"## 출처\n\n{citation_lines(citations)}\n\n"
        f"## 관련 노트\n\n{related_wikilinks(related) or '(없음)'}\n"
    )
