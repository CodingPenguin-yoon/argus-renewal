# Backend (Python)

FastAPI 기반 백엔드입니다. 도메인별 구조로 구성되어 있습니다.

## 구조
```text
src/
  domains/
    health/
      router.py
    news/
      data/
      providers/
      news_types.py
      provider.py
      factory.py
      service.py
      router.py
  config/
    env.py
  shared/
    errors.py
  main.py
```

## 설치
```bash
cd backend
python3 -m pip install -r requirements.txt
```

## 실행
```bash
python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 4000
```

## API
- `GET /health`
- `GET /api/news/top`
- `GET /api/news/search?q=NVDA`

## 확장
- `domains/news/provider.py` 인터페이스 유지
- `domains/news/providers`에 외부 API provider 추가
- `domains/news/factory.py`에서 provider 분기
