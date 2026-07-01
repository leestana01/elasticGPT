---
title: Kafka
tags: [kafka, streaming, infra]
created: 2026-06-01
updated: 2026-06-15
---

# Kafka

Apache Kafka는 대용량 이벤트 스트림을 안정적으로 주고받기 위한 분산 메시지 플랫폼이다. 이 프로젝트에서는 노트 변경과 색인 작업을 비동기로 연결하는 중추 역할을 한다. #kafka #streaming

## 핵심 개념

- **토픽(Topic)**: 이벤트가 쌓이는 이름 붙은 로그. 예: `rag.ingest`, `rag.retry`, `rag.dead-letter`.
- **파티션(Partition)**: 토픽을 여러 조각으로 나눠 병렬 처리와 순서 보장을 동시에 얻는다.
- **컨슈머 그룹(Consumer Group)**: 같은 그룹의 소비자들이 파티션을 나눠 맡아 수평 확장한다.
- **오프셋(Offset)**: 각 소비자가 어디까지 읽었는지 가리키는 위치 값. 커밋 시점 관리가 중요하다. #kafka

### 토픽 목록 예시

```bash
kafka-topics.sh --bootstrap-server localhost:9092 --list
# rag.ingest
# rag.retry
# rag.dead-letter
```

## 재시도와 실패 격리

소비자가 이벤트 처리에 실패하면 무한정 재시도하며 다른 이벤트를 막아선 안 된다. 그래서 로컬 재시도 → 재시도 토픽 → 최종 격리 순으로 단계를 둔다. 반복 실패한 이벤트가 최종적으로 이동하는 곳이 죽은 편지함이며, 자세한 내용은 [[Dead Letter Queue]] 를 참고한다.

### 프로젝트에서의 사용

전체 파이프라인 관점은 [[RAG 시스템 설계]] 에 정리돼 있고, 로컬 실행 구성은 [[Docker Compose 시뮬레이션]] 에서 다룬다. #streaming
