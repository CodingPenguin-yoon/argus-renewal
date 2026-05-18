# Frontend

Next.js App Router 기반 Argus v2 프론트엔드입니다.

## Routes

- `/argus`: 시장 판단
- `/argus/derivatives`: 옵션·선물
- `/argus/derivatives/futures`: KOSPI200 근월 선물
- `/argus/derivatives/option-quotes`: HTS형 옵션 시세표
- `/argus/derivatives/option-layer`: 당일 옵션 풋콜 레이어
- `/argus/derivatives/positions`: 주체별 포지션 종합 및 선물/옵션 레이어
- `/argus/reaction`: 현물 반응
- `/argus/triggers`: 뉴스 분석 메인
- `/argus/triggers/news`: 실시간 원천 뉴스 피드

Legacy `/krx*` route는 제거했습니다.

## Structure

```text
src/
  app/
    argus/
  argus_v2/
    components/
    contracts/
    lib/
    server/
```

## Env

```bash
BACKEND_BASE_URL=http://localhost:4000
```

## Run

```bash
pnpm --filter frontend dev
```

## Validation

```bash
pnpm --filter frontend lint
pnpm --filter frontend test -- --runInBand
pnpm --filter frontend build
```
