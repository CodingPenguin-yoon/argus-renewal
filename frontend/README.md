# Frontend

Next.js App Router 기반 Argus v2 프론트엔드입니다.

## Routes

- `/argus`: 시장 판단
- `/argus/derivatives`: 옵션·선물
- `/argus/reaction`: 현물 반응
- `/argus/triggers`: 뉴스 트리거

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
