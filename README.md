# ElasticGPT — Obsidian 기반 Kafka + Elasticsearch RAG 플랫폼

Obsidian Vault의 Markdown 지식을 Kafka 파이프라인으로 수집·색인하고, Elasticsearch 하이브리드 검색과 LLM으로 근거 기반 답변을 생성하는 RAG 플랫폼입니다. 질의응답에서 도출된 지식은 사용자 승인을 거쳐 다시 Obsidian note로 반영되어, 지식베이스가 점진적으로 개선되는 순환 구조를 갖습니다.

`docker compose up --build` 한 번으로 전체 시스템이 실행되며, OpenAI API key 없이도 Mock Provider로 전 과정을 시연할 수 있습니다.

## 아키텍처

```
[Mock Web UI] → [Backend API] → [Obsidian Vault]
                     ↓
   [Vault Watcher] → [Kafka] → [Workers] → [Elasticsearch]
                                    ↓
                              [AI Provider: Mock | OpenAI]
```

| 구성요소 | 역할 |
|---|---|
| Backend API (FastAPI) | Vault/Chat/Retrieval/Feedback/Note Update/Reindex API |
| Kafka | 파일 변경·파싱·청킹·임베딩·색인·지식갱신 이벤트 파이프라인 |
| Workers | Parser / Chunking / Embedding / Indexing / Knowledge Extraction / Note Update |
| Elasticsearch | note / chunk / graph edge / QA knowledge 색인 |
| PostgreSQL | vault, query/answer log, note update candidate, feedback, golden set |
| Redis | 임베딩 캐시 · idempotency |
| Mock Web UI | Chat, Citation, Retrieval Debug, Note Update, Indexing Status, DLQ |

## 사전 요구사항

- Docker Desktop (Docker Engine 24+) 및 Docker Compose v2
- 권장 메모리 8GB 이상 (Elasticsearch 힙 512MB 사용)
- (선택) OpenAI API key — 실제 임베딩/LLM을 쓰려는 경우에만 필요

## 빠른 시작

```bash
# 1) 환경 파일 준비 (키 없이도 동작)
cp .env.example .env

# 2) 전체 스택 빌드 및 실행
docker compose up --build
```

기동이 완료되면:

| 서비스 | 주소 |
|---|---|
| Mock Web UI | http://localhost:3000 |
| Backend API 문서 (Swagger) | http://localhost:8000/docs |
| Elasticsearch | http://localhost:9200 |

Sample Vault(`sample-vault/`)는 `/vault/sample`로 mount되어 기동 시 자동 등록됩니다.

## AI Provider 전환

`.env`에서 provider를 전환합니다.

```env
# Mock (기본값): 키 불필요, 결정론적 임베딩/답변
AI_PROVIDER=mock
OPENAI_API_KEY=

# OpenAI: 실제 API 사용
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
CHAT_MODEL=gpt-4.1-mini
```

`AI_PROVIDER=openai`라도 키가 비어 있으면 자동으로 Mock으로 폴백합니다. 두 provider 모두 임베딩 차원은 1536으로 고정되어 색인 mapping이 동일합니다.

## 데모 시나리오

> 아래 시나리오는 EPIC 단위로 순차 구현됩니다. Milestone 1(EPIC-01) 기준으로는 스택 기동·Sample Vault 자동 등록·상태 대시보드까지 확인할 수 있습니다.

### 샘플 질문
- "Kafka 기반 RAG 설계에서 DLQ는 어떻게 처리하기로 했지?"
- "Hybrid Search는 어떤 방식으로 동작해?"
- "Obsidian 자동 갱신 전략의 핵심은 무엇이야?"
- "Elasticsearch에서 벡터 검색은 어떻게 하나요?"

### Note Update 승인 시나리오
1. RAG Chat에서 질문 → citation 포함 답변 확인
2. Knowledge Extraction Worker가 저장 가치 있는 지식을 추출해 Note Update Candidate 생성
3. Web UI의 **Note Update Candidates**에서 Markdown preview 확인
4. 승인 시 실제 Markdown 파일 생성/갱신 → Vault Watcher가 감지 → 재색인

### DLQ 시뮬레이션
1. Embedding Worker에 강제 실패를 유발(예: 잘못된 이벤트 주입 또는 `FORCE_FAIL` 플래그)
2. local retry 후 최종 실패 시 `rag.dead-letter` topic으로 이동
3. Web UI의 **DLQ Viewer**에서 실패 이벤트 확인 후 재처리

## 프로젝트 구조

```
backend/            FastAPI API + Kafka workers (단일 이미지, WORKER_TYPE으로 역할 분기)
  app/
    api/            REST 라우터
    kafka/          topics · producer · consumer(재시도/DLQ)
    es/             Elasticsearch 클라이언트 · index mapping
    db/             SQLAlchemy 모델
    obsidian/       parser · chunker · watcher
    rag/            retrieval · context builder · generation
    providers/      mock · openai provider
    workers/        worker 핸들러 레지스트리
web/                정적 SPA(Mock Web UI) + nginx
sample-vault/       데모용 Obsidian Vault
```

## 서비스 목록

Docker Compose는 다음 서비스를 실행합니다: `kafka`, `elasticsearch`, `postgres`, `redis`, `backend-api`, `worker-parser`, `worker-chunker`, `worker-embedding`, `worker-indexing`, `worker-knowledge`, `worker-note-update`, `web`.

## 개발 노트

- 각 기능은 GitHub Issue(EPIC/User Story)에 대응하며 EPIC 단위 PR로 구현됩니다.
- `.env`는 `.gitignore` 처리되어 커밋되지 않습니다.
