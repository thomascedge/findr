# Findr

A geo-social API built with FastAPI, PostgreSQL, and Redis.

---

## Getting Started

### 1. Set up environment
```bash
cp .env.example .env   # add your SECRET_KEY
```

### 2. Start the stack
```bash
docker compose up --build
```

### 3. Verify it's running
Visit `http://localhost:8000/docs` for the interactive API.

---

## Docker Commands

### Starting & stopping
```bash
# Start all containers (builds image if needed)
docker compose up --build

# Start in the background
docker compose up -d

# Stop all containers
docker compose down

# Stop and delete all data volumes (wipes the database)
docker compose down -v
```

### Rebuilding
```bash
# Rebuild the app image after changing requirements.txt
docker compose up --build

# Rebuild without cache (nuclear option — full reinstall)
docker compose build --no-cache
```

### Logs
```bash
# Follow all container logs
docker compose logs -f

# Follow app logs only
docker compose logs -f app

# Follow db logs only
docker compose logs -f db
```

### Exec into containers
```bash
# Open a shell inside the app container
docker compose exec app bash

# Open a psql session directly in the db container
docker compose exec db psql -U postgres -d findr
```

### Running tests
```bash
docker compose exec app pytest tests/ -v
```

### Database
```bash
# Reset the database — drops all data and recreates tables on next startup
docker compose down -v && docker compose up --build
```

### Checking container status
```bash
# See all running containers and their health status
docker ps

# See all containers including stopped ones
docker ps -a
```

---

## Ports

| Service | Port |
|---|---|
| API | `http://localhost:8000` |
| API Docs | `http://localhost:8000/docs` |
| Postgres | `localhost:5432` |

---

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | Async Postgres connection string |
| `SECRET_KEY` | JWT signing secret — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DEBUG` | Enables SQLAlchemy query logging |

---

## Project Structure

```
findr/
├── app/
│   ├── api/
│   │   └── routes/              # Route handlers
│   │       ├── auth.py
│   │       ├── chats.py
│   │       ├── location.py
│   │       ├── messages.py
│   │       ├── user.py
│   │       └── ws.py
│   ├── core/                    # Auth, location, presence logic
│   │   ├── location.py
│   │   ├── presence.py
│   │   ├── redis.py
│   │   ├── security.py
│   │   └── variables.py
│   ├── models/
│   │   └── models.py            # SQLAlchemy models
│   ├── schemas/
│   │   └── schemas.py           # Pydantic schemas
│   ├── workers/                 # Celery background tasks
│   │   ├── celery_app.py
│   │   └── retention.py
│   ├── db.py                    # Database connection
│   └── main.py                  # FastAPI app entry point
├── migrations/                  # Alembic migrations
│   ├── versions/
│   │   └── 1f767692f59c_initial_schema.py
│   ├── env.py
│   └── script.py.mako
├── tests/
│   ├── endpoint/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_chats.py
│   │   ├── test_location.py
│   │   ├── test_messages.py
│   │   └── test_users.py
│   └── integration/
│       ├── conftest.py
│       └── test_ws.py
├── logs/
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── main.py
├── Makefile
├── pytest.ini
├── requirements.txt
└── ROADMAP.md
```