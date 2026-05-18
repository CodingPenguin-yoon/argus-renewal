# Argus Architecture

이 폴더는 Argus v2의 현재 아키텍처를 파트별로 설명합니다.

Argus는 한국장 초보-중급 투자자가 장 시작 전과 장중에 시장 상황을 빠르게 읽는 상황판입니다. 핵심 순서는 아래와 같습니다.

```text
파생/옵션 포지셔닝
-> 뉴스/매크로 트리거
-> 현물 반응
-> rule-based 판단 엔진
-> dashboard API
-> Next.js 화면
```

뉴스 분석은 두 층으로 나눕니다.

```text
뉴스 분석 > 메인
-> AI 판단을 거친 시장 연결 트리거

뉴스 분석 > 뉴스
-> AI 판단 전 원천 경제 뉴스 피드
```

## 문서 구성

1. [시스템 개요](01-system-overview.md)
   전체 런타임, 주요 경계, 데이터 흐름, 설계 원칙을 설명합니다.

2. [백엔드 API와 계약](02-backend-api-contracts.md)
   FastAPI route, Pydantic 계약, frontend Zod 계약의 관계를 설명합니다.

3. [스토리지와 데이터 모델](03-storage-data-model.md)
   SQLite 테이블, provider run, raw sample, snapshot 저장 방식을 설명합니다.

4. [Provider와 수집 파이프라인](04-provider-ingestion.md)
   KIS, RSS, Naver, DART, macro, mock/file provider가 내부 record로 바뀌는 과정을 설명합니다.

5. [판단 엔진](05-judgement-engine.md)
   파생/옵션, 뉴스, 현물 반응이 어떻게 시장 판단 라벨과 근거로 바뀌는지 설명합니다.

6. [프론트엔드 구조](06-frontend-architecture.md)
   Next.js route, 화면 shell, 상단 탭, 뉴스 분석 내부 탭, 상태 표시 구조를 설명합니다.

7. [뉴스 분석 아키텍처](07-news-analysis-architecture.md)
   AI 뉴스 트리거와 원천 뉴스 피드를 분리한 이유와 구현 방식을 설명합니다.

8. [운영과 검증](08-operations-validation.md)
   개발 서버, CLI, 검증 명령, 장애 확인 순서를 설명합니다.

## 읽는 순서

처음 보는 사람은 아래 순서가 좋습니다.

1. `01-system-overview.md`
2. `04-provider-ingestion.md`
3. `03-storage-data-model.md`
4. `05-judgement-engine.md`
5. `02-backend-api-contracts.md`
6. `06-frontend-architecture.md`
7. `07-news-analysis-architecture.md`
8. `08-operations-validation.md`

## 현재 기준

- 기준 날짜: 2026-05-14
- 주요 frontend route:
  - `/argus`
  - `/argus/derivatives`
  - `/argus/reaction`
  - `/argus/triggers`
  - `/argus/triggers/news`
- 주요 backend API:
  - `/api/argus/v2/dashboard`
  - `/api/argus/v2/news-feed`
  - `/health`
- 로컬 DB: SQLite
- frontend stack: Next.js App Router, TypeScript, Tailwind CSS, Zod
- backend stack: FastAPI, Pydantic, SQLite, provider/adapter 구조
