---
title: RAG 시스템 설계
tags: [rag, kafka, elasticsearch, design]
created: 2026-06-01
updated: 2026-06-15
---

# RAG 시스템 설계

Obsidian 볼트를 지식 소스로 삼고, [[Kafka]] 로 이벤트를 흘려보내며, [[Elasticsearch]] 에서 검색하는 RAG(Retrieval-Augmented Generation) 시스템의 설계 문서다. #rag #design

## 전체 아키텍처

파이프라인은 크게 네 단계로 나뉜다.

1. **수집**: Obsidian 노트가 변경되면 파일 감시기가 변경 이벤트를 `rag.ingest` 토픽으로 발행한다. #kafka
2. **색인**: 소비자가 노트를 청크로 나누고 임베딩을 계산해 [[Elasticsearch]] 에 저장한다.
3. **검색**: 질문이 오면 키워드와 벡터를 함께 쓰는 [[Hybrid Search]] 로 관련 청크를 찾는다.
4. **생성**: 검색된 문맥을 프롬프트에 넣어 LLM이 최종 답변을 만든다.

### 데이터 흐름

`노트 변경 → rag.ingest → 임베딩 → Elasticsearch 색인 → 검색 → 답변`

이 구조 덕분에 색인과 검색이 느슨하게 결합되고, 각 단계를 독립적으로 확장할 수 있다. #kafka

## 장애 처리

[[Kafka]] 소비자가 이벤트 처리에 실패하면 3단계로 대응한다.

1. **로컬 재시도**: 같은 소비자가 짧은 간격으로 몇 차례 즉시 재시도한다. (일시적 네트워크 오류 대비)
2. **재시도 토픽**: 로컬 재시도가 모두 실패하면 이벤트를 `rag.retry` 토픽으로 넘겨 지연 후 다시 처리한다.
3. **죽은 편지함**: 재시도 토픽에서도 계속 실패하면 최종적으로 `rag.dead-letter` 토픽으로 옮긴다. 이 뒤 처리는 [[Dead Letter Queue]] 문서를 따른다.

이렇게 하면 문제 이벤트가 파이프라인 전체를 막지 않고 격리된다. #rag

## 관련 문서

- 자동 갱신 규칙: [[Obsidian 자동 갱신 전략]]
- 로컬 실행 방법: [[Docker Compose 시뮬레이션]]
