---
title: Elasticsearch
tags: [elasticsearch, search, infra]
created: 2026-06-01
updated: 2026-06-15
---

# Elasticsearch

Elasticsearch는 역색인 기반의 분산 검색 엔진으로, 이 프로젝트에서 키워드 검색과 벡터 검색을 모두 담당한다. #elasticsearch #search

## 텍스트 검색

- **역색인(Inverted Index)**: 단어 → 문서 목록 매핑을 미리 만들어 두어 키워드 조회를 빠르게 한다.
- **BM25**: 단어 빈도(TF)와 문서 희소성(IDF)을 결합해 관련도를 매기는 기본 랭킹 함수다. 짧은 질의어의 정확한 일치에 강하다. #search

### 매핑 예시

```json
{
  "mappings": {
    "properties": {
      "content": { "type": "text" },
      "embedding": { "type": "dense_vector", "dims": 1536 }
    }
  }
}
```

## 벡터 검색

- **dense_vector**: 임베딩 벡터를 저장하는 필드 타입. 여기서는 1536차원 벡터를 쓴다.
- **kNN**: 질의 벡터와 가장 가까운 문서 벡터 k개를 찾는 근사 최근접 이웃 검색. 의미가 비슷하지만 단어가 다른 문서도 잡아낸다.

### 두 검색의 결합

BM25의 정확성과 kNN의 의미 이해를 함께 쓰면 검색 품질이 크게 오른다. 이 결합 방식은 [[Hybrid Search]] 에서 자세히 설명한다. 전체 시스템에서의 위치는 [[RAG 시스템 설계]] 를 참고한다. #elasticsearch
