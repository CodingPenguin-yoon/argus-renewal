# Deployment Collectors

Argus v2는 API와 collector를 별도 프로세스로 실행합니다.

```text
frontend
backend-api
market-collector
news-collector
shared SQLite DB
```

API 프로세스는 화면/API 요청을 처리하고, collector 프로세스는 외부 provider를 호출해 DB에 저장합니다. collector는 동일 DB 기준 lease를 잡기 때문에 같은 collector가 중복 실행되면 뒤에 뜬 프로세스는 `skipped`로 빠집니다.

## Commands

```bash
pnpm dev
pnpm dev:backend
pnpm dev:frontend
pnpm dev:collector:market
pnpm dev:collector:news
```

`pnpm dev` is for local development and starts all four processes from one terminal. Production should still run API and collectors as separate managed services.

직접 실행:

```bash
cd backend
python3 -m src.argus_v2.cli collect-loop --market-only --interval-seconds 60
python3 -m src.argus_v2.cli collect-loop --news-only --interval-seconds 300 --news-triggers-provider hybrid
```

## Docker Compose Shape

```yaml
services:
  backend:
    build: .
    working_dir: /app/backend
    command: python3 -m uvicorn src.main:app --host 0.0.0.0 --port 4000
    env_file:
      - backend/.env
    volumes:
      - argus-data:/app/backend/data

  market-collector:
    build: .
    working_dir: /app/backend
    command: python3 -m src.argus_v2.cli collect-loop --market-only --interval-seconds 60
    env_file:
      - backend/.env
    volumes:
      - argus-data:/app/backend/data
    restart: unless-stopped

  news-collector:
    build: .
    working_dir: /app/backend
    command: python3 -m src.argus_v2.cli collect-loop --news-only --interval-seconds 300 --news-triggers-provider hybrid
    env_file:
      - backend/.env
    volumes:
      - argus-data:/app/backend/data
    restart: unless-stopped

volumes:
  argus-data:
```

## systemd Shape

Backend:

```ini
[Unit]
Description=Argus backend API
After=network.target

[Service]
WorkingDirectory=/srv/argus_renewal/backend
EnvironmentFile=/srv/argus_renewal/backend/.env
ExecStart=/usr/bin/python3 -m uvicorn src.main:app --host 0.0.0.0 --port 4000
Restart=always

[Install]
WantedBy=multi-user.target
```

Market collector:

```ini
[Unit]
Description=Argus market collector
After=network.target

[Service]
WorkingDirectory=/srv/argus_renewal/backend
EnvironmentFile=/srv/argus_renewal/backend/.env
ExecStart=/usr/bin/python3 -m src.argus_v2.cli collect-loop --market-only --interval-seconds 60
Restart=always

[Install]
WantedBy=multi-user.target
```

News collector:

```ini
[Unit]
Description=Argus news collector
After=network.target

[Service]
WorkingDirectory=/srv/argus_renewal/backend
EnvironmentFile=/srv/argus_renewal/backend/.env
ExecStart=/usr/bin/python3 -m src.argus_v2.cli collect-loop --news-only --interval-seconds 300 --news-triggers-provider hybrid
Restart=always

[Install]
WantedBy=multi-user.target
```

## Defaults

- Market collector interval: 60 seconds.
- News collector interval: 300 seconds.
- Collector lease TTL: 180 seconds.
- Regular market collection: enabled.
- Night market collection: disabled.

Enable night derivatives with:

```env
ARGUS_COLLECTOR_NIGHT_MARKET_ENABLED=true
```
