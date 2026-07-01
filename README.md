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

전체 파이프라인(수집 → 색인 → RAG → 자동 갱신 → 평가)이 구현되어 있으며, Mock Web UI에서 아래 흐름을 모두 시연할 수 있습니다.

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
1. 잘못된 이벤트를 파이프라인 topic에 주입 (예: 필수 필드 누락한 `obsidian.note.parsed`)
   ```bash
   docker compose exec -T kafka bash -lc \
     'echo "{\"event_id\":\"evt_bad\",\"schema_version\":1}" | \
      /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic obsidian.note.parsed'
   ```
2. validation 오류(PermanentError)는 재시도 없이 `rag.dead-letter`로 이동 → `worker-ops`가 DB에 영속화
3. Web UI의 **DLQ Viewer**에서 실패 topic·consumer·error·payload 확인 후 **재처리** 버튼으로 원본 topic 재발행

## 주요 API

| 영역 | 엔드포인트 |
|---|---|
| Vault | `GET/POST /api/vaults` |
| RAG Chat | `POST /api/rag/chat` |
| Retrieval Debug | `POST /api/retrieval/debug`, `GET /api/retrieval/chunk?chunkId=` |
| Graph | `GET /api/graph/backlinks`, `GET /api/graph/links` |
| Note Update | `GET /api/note-updates`, `POST /api/note-updates/{id}/approve\|reject` |
| Feedback | `POST /api/feedback` |
| 운영 | `GET /api/dlq`, `POST /api/dlq/{id}/reprocess`, `POST/GET /api/reindex`, `GET /api/metrics`, `GET /api/indexing/status` |
| 평가 | `GET/POST /api/eval/golden`, `POST /api/eval/run`, `GET /api/eval/runs`, `GET /api/eval/compare` |

전체 스키마는 http://localhost:8000/docs 참고.

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

## 구현 현황

INIT-01 이하 10개 EPIC / 49개 User Story가 EPIC 단위 PR로 모두 구현·머지되었습니다.

| EPIC | 내용 |
|---|---|
| 01 | Docker Compose 데모 실행 환경, Sample Vault, Mock/OpenAI Provider |
| 02 | Vault 등록 API, 폴링 기반 Vault Watcher, file changed 이벤트 |
| 03 | Kafka Ingestion Pipeline (Parser/Chunker/Embedding/Indexing) |
| 04 | Elasticsearch 인덱스 매핑·versioning·alias |
| 05 | Hybrid Retrieval + Context Builder + Answer Generation + Chat API |
| 06 | Obsidian Graph Expansion (wikilink/backlink, boost) |
| 07 | 질의응답 기반 Obsidian 자동 갱신 루프 (승인/거절, 신규/append, feedback) |
| 08 | Mock Web UI (Dashboard/Chat/Citation/Retrieval Debug/Note Update/Indexing/DLQ) |
| 09 | 운영 안정성 (retry/DLQ/idempotency/reindex/metrics) |
| 10 | 품질 평가 (Golden Set, Recall@K/MRR, citation/groundedness) |

## 설계 결정 및 알려진 한계

프로젝트 진행 중 아래 사항은 합리적 기본값으로 자율 결정했습니다.

- **AI Provider**: `.env`의 `AI_PROVIDER=openai`로 실제 임베딩/LLM을 사용하도록 설정했습니다. 키가 없거나 `mock`이면 결정론적 Mock으로 자동 폴백합니다. 임베딩 차원은 provider와 무관하게 1536으로 고정해 색인 mapping을 통일했습니다.
- **Vault Watcher**: Docker bind mount(특히 macOS)에서 inotify가 신뢰성 없게 동작하므로 `PollingObserver`를 사용합니다.
- **Graph edge 해석**: 색인 순서/refresh 지연에 영향을 받지 않도록 backlink/outgoing 해석을 쿼리 시점에 수행합니다.
- **Milestone/우선순위**: EPIC 단위로 부여하고 하위 User Story가 상속합니다.
- **자동화 테스트**: 별도 단위 테스트 파일은 추가하지 않았고, 각 EPIC을 실제 스택에서 end-to-end(REST·Kafka·ES 검증, Web UI는 Playwright)로 검증했습니다. 후속 작업으로 pytest 스위트 추가를 권장합니다.
- **알려진 한계 — Out-of-domain 회피(abstain)**: 평가 결과 `abstainAccuracy = 0.0`. Hybrid Retrieval이 관련 없는 질문에도 항상 top chunk를 반환하고 생성 단계가 이를 근거로 답하기 때문에, 도메인 밖 질문에서 "모른다"고 보류하지 못하는 경우가 있습니다. 개선 방향은 retrieval score 하한(relevance gate)을 두어 근거가 약하면 insufficient로 처리하는 것입니다. 평가 프레임워크는 이 한계를 정량적으로 탐지합니다.

## 참고

- `.env`는 `.gitignore` 처리되어 커밋되지 않습니다 (`.env.example` 참고).
- 각 기능은 GitHub Issue(EPIC/User Story)에 대응하며 EPIC 단위 PR로 구현되었습니다.
