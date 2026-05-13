# 04. 왜 이런 구조를 쓰나

이 문서는 Argus가 왜 provider, storage, dashboard, judgement, frontend를 나눠서 쓰는지 설명합니다.

결론부터 말하면 구조를 나누는 이유는 멋있어 보이려고가 아닙니다.

장중에 문제가 생겼을 때 빨리 원인을 찾고, 외부 API가 흔들려도 화면과 판단이 덜 흔들리게 하려는 것입니다.

## 1. API 파일 하나에 다 넣으면 왜 안 좋은가

처음에는 이렇게 만들고 싶을 수 있습니다.

```text
API에서 KIS 호출
API에서 RSS 호출
API에서 Gemini 호출
API에서 DB 저장
API에서 판단
API에서 화면 응답
```

작은 실험에서는 빠릅니다.

하지만 Argus 같은 금융 데이터 앱에서는 금방 문제가 생깁니다.

문제:

- API 파일이 너무 커집니다.
- 외부 API 하나가 느리면 화면 전체가 느려집니다.
- KIS token 문제가 화면 API 장애로 바로 번집니다.
- Gemini timeout이 화면 로딩 지연으로 이어집니다.
- DB 저장과 화면 응답 책임이 섞입니다.
- 테스트하기 어렵습니다.
- “데이터가 안 들어온 건지, 화면이 못 보여주는 건지” 구분하기 어렵습니다.

그래서 Argus는 수집과 조회를 분리합니다.

## 2. 역할을 나누면 무엇이 좋아지나

Argus 역할 분리:

```text
CLI = 수집 명령 실행
Provider = 외부 데이터 가져오기
Storage = DB 저장/조회
Dashboard Builder = 화면용 데이터 조립
Judgement Engine = 시장 판단
API = dashboard 전달
Frontend = 화면 표시
```

좋은 점:

- 장애 위치를 빠르게 찾을 수 있습니다.
- 외부 API 응답이 바뀌어도 provider만 고치면 됩니다.
- DB 구조가 바뀌어도 storage 중심으로 고치면 됩니다.
- frontend는 KIS/Gemini/RSS 내부 구조를 몰라도 됩니다.
- 테스트를 작은 단위로 나눌 수 있습니다.
- SQLite에서 PostgreSQL로 갈 때 변경 범위가 줄어듭니다.

## 3. 의존성 방향

의존성은 “누가 누구를 알고 있나”입니다.

나쁜 방향:

```text
frontend가 KIS 응답 field를 안다
frontend가 Gemini key를 안다
judgement engine이 RSS item 구조를 안다
API가 모든 외부 provider 구현을 안다
```

좋은 방향:

```text
provider만 외부 API 구조를 안다
storage만 DB 저장 규칙을 안다
dashboard builder만 화면용 조립을 안다
frontend는 MarketDashboard contract만 안다
judgement engine은 정리된 구조 데이터만 안다
```

이렇게 하면 한쪽이 바뀌어도 전체가 덜 흔들립니다.

## 4. Provider를 따로 두는 이유

외부 API는 현실적으로 불안정합니다.

가능한 문제:

- 응답 field가 문서와 다릅니다.
- 빈 배열이 옵니다.
- timeout이 납니다.
- rate limit이 걸립니다.
- 인증 token이 만료됩니다.
- 일부 endpoint만 실패합니다.
- 시장 시간에 따라 응답이 달라집니다.

이런 지저분함을 화면과 판단 엔진으로 흘려보내면 안 됩니다.

provider는 외부의 지저분함을 받아 내부 record로 정리하는 방어막입니다.

Argus 내부에서는 이렇게 정리된 record를 씁니다.

```text
Derivatives snapshot
Option chain snapshot
Market reaction snapshot
News trigger record
```

## 5. Storage를 따로 두는 이유

DB 코드를 여기저기 흩뿌리면 관리가 어려워집니다.

나쁜 예:

```text
provider 안에서 직접 INSERT
dashboard 안에서 직접 복잡한 SELECT
API 안에서 직접 raw sample 저장
test 안에서 임의 테이블 생성
```

문제:

- 저장 규칙이 파일마다 달라집니다.
- redaction이 빠질 수 있습니다.
- 어떤 테이블을 누가 쓰는지 찾기 어렵습니다.
- DB 구조 변경 시 영향 범위가 커집니다.

Argus는 storage에 DB 책임을 모읍니다.

```text
backend/src/argus_v2/storage.py
```

storage가 있으면 좋은 점:

- 저장 규칙이 한 곳에 있습니다.
- raw sample redaction을 일관되게 처리합니다.
- provider run 기록이 일관됩니다.
- dashboard는 storage 조회 결과를 믿을 수 있습니다.

## 6. Contract를 따로 두는 이유

contract는 약속입니다.

backend와 frontend가 같은 약속을 보지 않으면 화면은 쉽게 깨집니다.

예:

```text
backend는 ai_confidence를 confidence로 보낸다
frontend는 ai_confidence를 기대한다
```

이런 차이가 있으면 화면에서 값이 안 보입니다.

Argus는 양쪽에 contract를 둡니다.

backend:

```text
backend/src/argus_v2/contracts.py
```

frontend:

```text
frontend/src/argus_v2/contracts/dashboard.ts
```

좋은 점:

- 필드 추가/삭제 영향이 보입니다.
- frontend가 잘못된 JSON을 빨리 감지합니다.
- 테스트가 명확해집니다.

## 7. 왜 DB를 먼저 거치나

장중 대시보드는 빠르고 안정적이어야 합니다.

외부 API를 화면 요청마다 직접 부르면 안 됩니다.

문제:

- KIS가 느리면 화면이 느립니다.
- Gemini가 timeout이면 화면이 멈춥니다.
- RSS가 실패하면 뉴스 영역이 불안정합니다.
- 같은 화면을 새로고침할 때마다 판단 근거가 달라질 수 있습니다.
- 과거와 현재를 비교하기 어렵습니다.

DB를 거치면:

- 화면은 빠르게 최신 저장값을 읽습니다.
- 외부 API 실패와 화면 장애를 분리할 수 있습니다.
- provider run 기록으로 실패 원인을 추적할 수 있습니다.
- 직전 snapshot과 비교할 수 있습니다.

## 8. 왜 raw sample을 저장하나

금융 API는 실제 응답이 문서와 다를 수 있습니다.

나중에 이런 질문이 생깁니다.

```text
KIS가 실제로 basis 값을 어떤 필드명으로 줬지?
옵션체인 level이 100건 들어왔나?
현물 투자자 수급 단위가 원인가, 만원인가?
RSS 원문 link가 어떤 값이었지?
Gemini가 왜 이 뉴스를 버렸지?
```

raw sample이 있으면 확인할 수 있습니다.

하지만 secret은 저장하면 안 됩니다.

그래서 redaction이 필요합니다.

## 9. 왜 AI 판단을 키워드 규칙 대신 쓰나

뉴스는 문자열 키워드만으로 판단하기 어렵습니다.

예:

```text
금리 상승
```

이 말은 보통 위험자산에 부담입니다.

하지만 문맥에 따라 다를 수 있습니다.

예:

```text
금리 상승 우려 완화
```

문자열에 “금리 상승”이 있다고 무조건 악재로 보면 안 됩니다.

또 다른 예:

```text
반도체 급등주 무료추천
```

반도체라는 단어가 있어도 시장 판단에 쓸 뉴스가 아닐 수 있습니다.

그래서 Argus는 실뉴스 판단에 AI JSON을 씁니다.

AI가 봐야 하는 것:

- 출처 신뢰도.
- 한국장 지수와의 연결성.
- 파생/옵션과의 연결성.
- 매크로 영향.
- 프로모션/리딩방/추천주 여부.
- 실제 시장 판단에 쓸 가치.

## 10. 그래도 AI를 무조건 믿으면 안 되는 이유

AI도 틀릴 수 있습니다.

가능한 문제:

- 출처를 잘못 평가할 수 있습니다.
- 너무 보수적으로 `should_use=false`를 줄 수 있습니다.
- 너무 많은 factors를 붙일 수 있습니다.
- 영어로 reason을 줄 수 있습니다.
- rate limit이나 timeout이 날 수 있습니다.

그래서 Argus는 AI 판단을 구조화해서 저장합니다.

```text
should_use
impact
relevance_score
connection_strength
confidence
summary
reason
affected_factors
```

이렇게 저장하면 나중에 판단을 검토하고 prompt를 보정할 수 있습니다.

## 11. 왜 AI 후보를 먼저 제한하나

AI에 모든 뉴스를 보내면 안 됩니다.

문제:

- 비용 증가.
- timeout 증가.
- 429 Too Many Requests.
- 잡음 뉴스 증가.
- 장중 수집 속도 저하.

Argus는 먼저 후보를 줄입니다.

```text
최신순 정렬
-> query term 매칭
-> 후보 수 제한
-> AI 판단
```

현재 기본값:

```text
ARGUS_NEWS_TRIGGERS_LIMIT=3
ARGUS_NEWS_AI_TIMEOUT_SECONDS=8
```

이 값은 완성값이 아닙니다.

장중 운영을 보면서 조정해야 합니다.

## 12. 왜 mock을 유지하나

mock은 가짜 데이터라 없어도 될 것 같지만 중요합니다.

필요한 이유:

- API key 없이도 실행됩니다.
- 새로 켠 개발 환경에서도 화면이 깨지지 않습니다.
- 외부 API 장애가 있어도 frontend 작업이 가능합니다.
- 테스트를 안정적으로 만들 수 있습니다.

Argus 원칙:

```text
run without external API keys
```

그래서 mock fallback은 유지합니다.

## 13. 왜 provider health를 보여주나

사용자가 봐야 하는 것은 판단뿐만이 아닙니다.

그 판단이 어떤 데이터 상태에서 나온 것인지도 봐야 합니다.

예:

```text
파생 데이터 fresh
옵션체인 fresh
뉴스 trigger missing
현물 반응 partial
```

이 상태라면 판단을 완전히 믿기보다 조심해서 봐야 합니다.

provider health는 대시보드의 안전장치입니다.

## 14. 왜 테스트를 너무 많이 쓰지 않나

테스트는 필요합니다.

하지만 지금 단계에서 테스트가 개발을 잡아먹으면 안 됩니다.

Argus에서 꼭 지켜야 하는 테스트:

- backend contract가 깨지지 않는가.
- frontend contract가 깨지지 않는가.
- KIS token을 env에 직접 넣지 않아도 되는가.
- raw sample에서 secret이 redaction되는가.
- RSS live 뉴스가 AI 판단 없이는 임의 분류되지 않는가.
- AI 후보 제한이 실제로 호출 수를 줄이는가.
- DB가 비어 있으면 mock fallback이 동작하는가.

지금 우선순위가 낮은 테스트:

- 과도한 UI snapshot.
- 스타일만 확인하는 테스트.
- 구현 세부사항에 너무 묶인 테스트.

## 15. 지금 구조의 한계

현재 구조는 좋은 출발점이지만 완성형은 아닙니다.

한계:

- KOSPI200 시장 전체 선물 수급 endpoint가 아직 확정되지 않았습니다.
- KIS 보조 API 일부는 장중 반복 관찰이 필요합니다.
- Gemini prompt는 실제 장중 사례를 보며 보정해야 합니다.
- 판단 엔진 가중치는 1차 버전입니다.
- 매크로 source는 아직 결정해야 합니다.
- 자동 수집 스케줄러는 아직 붙이지 않았습니다.

하지만 큰 방향은 맞습니다.

먼저 데이터 계약과 저장 구조를 안정화하고, 그 위에 provider와 판단 품질을 올리는 순서입니다.

## 16. 새 기능을 붙일 때 순서

예를 들어 “경제 캘린더 source를 붙이자”고 하면 순서는 이렇습니다.

```text
1. 어떤 정보가 필요한지 PRD 기준으로 정한다.
2. 내부 record/contract를 정한다.
3. provider를 만든다.
4. 외부 응답을 내부 record로 바꾼다.
5. raw sample을 redaction해서 저장한다.
6. storage 저장/조회 함수를 만든다.
7. dashboard builder에 연결한다.
8. judgement engine에서 쓸지 정한다.
9. frontend에 표시한다.
10. 핵심 테스트를 추가한다.
11. 문서를 업데이트한다.
```

이 순서를 지키면 코드가 덜 엉킵니다.

## 17. 코드를 읽을 때 질문

파일을 열 때 아래 질문을 먼저 던집니다.

```text
이 파일은 가져오는 담당인가?
저장하는 담당인가?
조립하는 담당인가?
판단하는 담당인가?
보여주는 담당인가?
설정하는 담당인가?
```

답이 여러 개라면 그 파일은 너무 많은 일을 하고 있을 가능성이 있습니다.

## 18. 한 줄 결론

Argus 구조는 복잡해 보이지만 핵심은 단순합니다.

```text
외부 API의 지저분함은 provider가 막고,
DB 기록은 storage가 책임지고,
화면은 contract로 정리된 결과만 받는다.
```
