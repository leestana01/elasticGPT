---
title: Obsidian
tags: [obsidian, knowledge, markdown]
created: 2026-06-01
updated: 2026-06-15
---

# Obsidian

Obsidian은 로컬 마크다운 파일을 지식 그래프로 다루는 노트 앱이다. 이 프로젝트에서는 볼트(vault)가 RAG의 지식 소스가 된다. #obsidian #knowledge

## 볼트와 마크다운

- **볼트(Vault)**: 노트가 담긴 폴더 전체. 모든 노트는 순수 마크다운 파일이라 파싱과 색인이 쉽다.
- **프론트매터(Frontmatter)**: 파일 맨 위 YAML 블록. `title`, `tags`, `created`, `updated` 같은 메타데이터를 담아 필터링과 정렬에 활용한다. #markdown

### 프론트매터 예시

```yaml
---
title: Obsidian
tags: [obsidian, knowledge, markdown]
created: 2026-06-01
updated: 2026-06-15
---
```

## 링크와 그래프

- **위키링크(Wikilink)**: `[[노트 제목]]` 형식으로 노트끼리 연결한다. 별칭이 필요하면 [[RAG 시스템 설계|RAG 설계]] 처럼 파이프로 표시명을 바꾼다.
- **백링크(Backlink)**: 나를 가리키는 다른 노트 목록. 역방향 탐색으로 맥락을 넓힐 수 있다.
- 이 연결 구조가 그래프를 이루며, 검색 시 관련 노트를 함께 끌어오는 데 유용하다.

### 검색과의 연계

노트 본문과 링크 구조는 색인 대상이 된다. 키워드와 벡터를 함께 쓰는 방식은 [[Hybrid Search]] 에서 다룬다. #knowledge
