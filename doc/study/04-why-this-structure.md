# 04. 왜 이런 구조를 쓰나

## 1. API 파일 하나에 다 넣으면 안 되나

작은 실험 프로젝트라면 API 파일 하나에 다 넣어도 됩니다.

예를 들면:

```text
API에서 Naver 호출
API에서 DART 호출
API에서 KIS 호출
API에서 DB 저장
API에서 판단
API에서 화면 응답
```

처음에는 빨라 보입니다. 하지만 조금만 커지면 문제가 생깁니다.

- API 파일이 너무 커집니다.
- 테스트하기 어렵습니다.
- 외부 API 하나 바꾸면 화면 API까지 흔들립니다.
- 데이터 저장과 화면 응답 책임이 섞입니다.
- 장애 원인을 찾기 어렵습니다.

그래서 역할을 나눕니다.

## 2. 역할을 나누면 뭐가 좋아지나

Argus는 이렇게 나눕니다.

```text
API = 요청 받고 응답하기
Provider = 외부 데이터 가져오기
Storage = DB 저장/조회하기
Dashboard Builder = 화면용 데이터 조립하기
Judgement Engine = 시장 판단하기
Frontend = 보여주기
```

좋은 점은 명확합니다.

- 어디가 문제인지 빨리 찾을 수 있습니다.
- 외부 API를 바꿔도 화면 코드를 덜 건드립니다.
- 테스트를 작게 나눌 수 있습니다.
- 나중에 SQLite에서 PostgreSQL로 바꾸기 쉽습니다.
- Naver 대신 다른 뉴스 API를 붙이기 쉽습니다.

## 3. 좋은 구조는 “멋있는 구조”가 아닙니다

구조를 나누는 이유는 멋있어 보이려고가 아닙니다.

좋은 구조는 이런 질문에 빨리 답하게 해줍니다.

```text
데이터가 안 들어왔나?
들어왔는데 저장이 안 됐나?
저장은 됐는데 dashboard가 못 읽나?
dashboard는 읽었는데 판단 엔진이 이상한가?
판단은 맞는데 화면 표시가 이상한가?
```

Argus 구조는 이 질문을 따라가면서 디버깅할 수 있게 만들어져 있습니다.

## 4. 의존성 방향

개발에서 의존성은 “누가 누구를 알고 있나”입니다.

나쁜 방향:

```text
frontend가 KIS API 구조를 안다
frontend가 DART API 키를 안다
API가 Naver 응답 필드 하나하나를 다 안다
judgement engine이 외부 API별 필드명을 안다
```

좋은 방향:

```text
provider만 외부 API를 안다
storage만 DB 저장 방식을 안다
dashboard builder만 화면용 조립 방식을 안다
frontend는 MarketDashboard contract만 안다
```

이렇게 하면 한쪽이 바뀌어도 전체가 덜 흔들립니다.

## 5. Contract가 중요한 이유

contract는 약속입니다.

backend와 frontend 사이에는 이런 약속이 있습니다.

```text
MarketDashboard 형태로 데이터를 준다.
```

이 약속이 없으면 frontend는 backend가 뭘 줄지 매번 불안합니다.

contract가 있으면:

- backend 응답 모양이 고정됩니다.
- frontend가 안전하게 화면을 만들 수 있습니다.
- 테스트가 쉬워집니다.
- 나중에 필드를 추가할 때 영향 범위가 보입니다.

## 6. Provider를 따로 두는 이유

외부 API는 믿을 수 없습니다.

이 말은 외부 API가 나쁘다는 뜻이 아닙니다. 현실적으로 이런 일이 자주 생긴다는 뜻입니다.

- 응답 필드명이 문서와 다릅니다.
- 빈 데이터가 올 수 있습니다.
- 인증이 실패할 수 있습니다.
- 속도가 느릴 수 있습니다.
- 장애가 날 수 있습니다.
- rate limit이 걸릴 수 있습니다.

그래서 외부 API와 직접 대화하는 코드를 provider 안에 둡니다.

provider가 외부의 지저분함을 막아주고, Argus 내부에는 정리된 record만 넘깁니다.

## 7. Storage를 따로 두는 이유

DB 코드를 여기저기 흩뿌리면 곧 관리가 어려워집니다.

예를 들어 여러 파일에서 직접 SQL을 쓰면:

- 어떤 테이블에 누가 쓰는지 찾기 어렵습니다.
- 저장 규칙이 파일마다 달라질 수 있습니다.
- redaction 같은 보안 처리가 빠질 수 있습니다.
- 테스트가 어렵습니다.

그래서 storage에 DB 저장/조회 책임을 모읍니다.

Argus에서는 raw sample을 저장할 때 민감값을 지우는 규칙도 storage에 들어 있습니다.

## 8. 수집과 조회를 분리하는 이유

Argus에서 가장 중요한 구조 중 하나입니다.

```text
수집 = 외부 API 호출
조회 = DB 읽기
```

수집은 실패할 수 있고 느릴 수 있습니다. 조회는 빨라야 합니다.

화면은 빠르게 떠야 하므로 조회만 합니다. 수집은 CLI나 스케줄러가 따로 합니다.

이 구조는 금융 도구에 특히 중요합니다. 장중에 화면을 자주 봐야 하는데, 매번 외부 API가 느리면 사용성이 나빠집니다.

## 9. Mock을 유지하는 이유

mock은 가짜 데이터라서 없어도 될 것 같지만, 실제로는 중요합니다.

mock이 있으면:

- API 키 없이도 화면 개발이 가능합니다.
- 새 개발자가 바로 프로젝트를 실행할 수 있습니다.
- 외부 API 장애와 관계없이 테스트할 수 있습니다.
- 빈 DB에서도 화면이 깨지지 않습니다.

Argus는 “run without external API keys” 원칙이 있습니다. 그래서 mock은 계속 필요합니다.

## 10. Redaction을 강제하는 이유

외부 API raw payload를 저장하면 디버깅에 좋습니다. 하지만 token이나 secret이 같이 저장되면 위험합니다.

그래서 Argus는 민감한 key를 저장 전에 가립니다.

```text
access_token
authorization
appsecret
client_secret
token
```

이런 값은 `[REDACTED]`로 바뀝니다.

금융 데이터 도구에서는 이 습관이 중요합니다.

## 11. 왜 DB에 provider run을 저장하나

provider run은 운영 기록입니다.

나중에 이런 질문이 생깁니다.

```text
오늘 뉴스가 왜 안 보이지?
Naver 키가 없어서 skipped인가?
RSS는 성공했는데 필터 때문에 0건인가?
DART가 장애였나?
KIS 옵션체인은 몇 건 들어왔나?
```

provider run이 없으면 감으로 추측해야 합니다. provider run이 있으면 기록으로 확인할 수 있습니다.

## 12. 왜 hybrid provider가 있나

뉴스는 한 source만 보면 약합니다.

RSS는 키 없이 쉽지만 제한적입니다. Naver는 검색성이 좋습니다. DART는 공식 공시라 신뢰도가 높지만 뉴스 문맥은 약합니다.

그래서 `hybrid` 모드가 있습니다.

```text
RSS + Naver + DART
```

Argus는 이 여러 source를 뉴스 트리거라는 한 모양으로 맞춥니다.

## 13. 좋은 테스트는 무엇인가

테스트를 너무 많이 만들면 개발 속도가 떨어집니다. 하지만 핵심 계약은 테스트해야 합니다.

Argus에서 중요한 테스트는 이런 것입니다.

- API가 `MarketDashboard` 모양을 지키는가
- provider raw sample에서 secret이 지워지는가
- KIS token을 env에 직접 넣지 않아도 되는가
- Naver provider가 올바른 헤더를 보내는가
- DART provider가 올바른 파라미터를 보내는가
- DB가 비어 있을 때 mock fallback이 동작하는가

반대로 너무 세세한 UI snapshot 테스트는 지금 단계에서 우선순위가 낮습니다.

## 14. 지금 구조의 한계

현재 구조도 완성형은 아닙니다.

남은 한계는 이렇습니다.

- 현물 반응 live provider가 아직 약합니다.
- 뉴스 중요도 필터가 아직 단순합니다.
- KIS 선물 수급/basis/OI 변화율이 아직 보강 필요합니다.
- 판단 엔진 점수 규칙이 아직 1차 버전입니다.

하지만 큰 방향은 맞습니다. 먼저 데이터 계약과 저장 구조를 잡고, 그 위에 provider와 판단 품질을 올리는 순서입니다.

## 15. 공부 순서

처음부터 모든 코드를 이해하려고 하면 어렵습니다.

이 순서로 보면 좋습니다.

1. `README.md`에서 전체 실행 방법을 봅니다.
2. `doc/study/01-big-picture.md`로 전체 그림을 봅니다.
3. `doc/study/02-terms.md`로 용어를 익힙니다.
4. `backend/src/argus_v2/cli.py`에서 수집 명령을 봅니다.
5. `backend/src/argus_v2/providers/context_inputs.py`에서 provider 예시를 봅니다.
6. `backend/src/argus_v2/storage.py`에서 DB 저장을 봅니다.
7. `backend/src/argus_v2/dashboard.py`에서 화면용 조립을 봅니다.
8. `backend/src/argus_v2/api/router.py`에서 API 입구를 봅니다.
9. `frontend/src/argus_v2/components/dashboard.tsx`에서 화면 표시를 봅니다.

## 16. 코드를 읽을 때 질문

파일을 볼 때 아래 질문을 던지면 됩니다.

```text
이 파일은 가져오는 담당인가?
저장하는 담당인가?
조립하는 담당인가?
판단하는 담당인가?
보여주는 담당인가?
```

답이 여러 개라면 파일이 너무 많은 일을 하고 있을 가능성이 있습니다.

## 17. 새 기능을 붙일 때 순서

예를 들어 “새 경제 캘린더 source를 붙이자”고 하면 순서는 이렇습니다.

```text
1. 어떤 데이터가 필요한지 contract를 정한다.
2. provider를 만든다.
3. raw sample을 redaction해서 저장한다.
4. storage 조회 함수를 만든다.
5. dashboard builder에 연결한다.
6. judgement engine에서 쓸지 정한다.
7. frontend에 보여준다.
8. 핵심 테스트를 추가한다.
```

이 순서를 지키면 코드가 덜 엉킵니다.

## 18. 한 줄 결론

Argus 구조는 복잡해 보이지만 핵심은 단순합니다.

```text
외부 데이터의 지저분함은 provider가 막고,
DB 기록은 storage가 책임지고,
화면은 contract로 정리된 결과만 받는다.
```
