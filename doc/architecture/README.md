# Architecture Docs

`architecture/`는 현재 코드베이스를 설명하는 문서의 진입점입니다.

## 읽는 순서
1. `implementation-status.md`
2. `system-map.md`
3. `project-structure.md`
4. `krx-mvp-ia.md`

## 문서 역할
- `implementation-status.md`
  - 현재 구현 범위, 남은 작업, 문서 체계를 빠르게 파악할 때 봅니다.
- `system-map.md`
  - frontend, backend, scripts, doc 사이의 큰 연결 구조를 볼 때 봅니다.
- `project-structure.md`
  - 실제 디렉터리와 주요 파일 책임을 찾을 때 봅니다.
- `krx-mvp-ia.md`
  - 현재 KRX 화면 IA와 사용자 표면 명칭을 확인할 때 봅니다.

## 원칙
- 현재 사실만 적습니다.
- 세부 설계나 도메인별 운영 메모는 `../domains/`로 보냅니다.
- 남은 작업과 과거 계획은 `../plans/`로 보냅니다.
