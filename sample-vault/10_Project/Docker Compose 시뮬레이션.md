---
title: Docker Compose 시뮬레이션
tags: [docker, infra, simulation]
created: 2026-06-01
updated: 2026-06-15
---

# Docker Compose 시뮬레이션

이 데모 전체를 로컬에서 한 번에 띄우기 위한 Docker Compose 구성을 설명한다. [[Kafka]], [[Elasticsearch]], 그리고 애플리케이션 서비스가 하나의 네트워크 안에서 함께 실행된다. #docker #infra

## 실행 방법

프로젝트 루트에서 아래 명령 한 줄이면 모든 컨테이너가 빌드되고 기동된다.

```bash
docker compose up --build
```

종료는 `docker compose down`, 볼륨까지 지우려면 `docker compose down -v` 를 쓴다. #docker

## 서비스 구성

핵심 서비스는 메시지 브로커, 검색 엔진, 그리고 파이프라인 애플리케이션이다.

```yaml
services:
  kafka:
    image: bitnami/kafka:3.7
    ports:
      - "9092:9092"
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
  app:
    build: .
    depends_on:
      - kafka
      - elasticsearch
```

### 기동 순서 주의

애플리케이션은 [[Kafka]] 와 [[Elasticsearch]] 가 먼저 준비되어야 한다. `depends_on` 은 컨테이너 시작 순서만 보장하고 내부 준비 완료까지는 기다려 주지 않으므로, 애플리케이션 쪽에서 헬스 체크와 재시도 로직을 함께 두는 편이 안전하다.

## 검증 팁

- `curl localhost:9200` 로 Elasticsearch 응답을 확인한다.
- 카프카 토픽이 정상 생성됐는지 컨테이너 로그로 점검한다. #infra
