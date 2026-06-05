# Findr 🗺️

Findr is a geo-social API for connecting people nearby in real time. Built for Austin's queer community as its first market, it puts you on a live map with people around you — swipe, chat, and meet up.

This is the backend: a FastAPI + PostgreSQL + Redis stack with real-time WebSocket presence, photo moderation, Celery workers, and a full compliance pipeline for legal operation.

---

## What's inside

- **Real-time map** — WebSocket presence with geohash pub/sub, so users see each other appear and disappear live
- **Messaging** — DMs and group chats with soft delete and 90-day retention
- **Photos** — Upload pipeline with AWS Rekognition moderation running in the background
- **Auth** — JWT with email verification, password reset, and token blacklisting on logout
- **Legal** — Age verification (18+), CCPA data export/deletion, FOSTA-SESTA user reporting, account hard-delete worker
- **Search** — Username and bio keyword search, with optional proximity filter

---

## Getting started

### 1. Copy the env file and fill in your secrets

```bash
cp .env.example .env
```

The only thing you strictly need to get running locally is a `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Everything else (AWS, SES, S3) is handled by LocalStack automatically.

### 2. Start the stack

```bash
docker compose up --build
```

This spins up Postgres, Redis, the FastAPI app, two Celery containers (worker + beat scheduler), and LocalStack for AWS services.

### 3. Check it's running

```
http://localhost:8000/docs     ← interactive API docs
http://localhost:8000/health   ← health check
```

---

## Environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | Async Postgres connection string (`postgresql+asyncpg://...`) |
| `SYNC_DATABASE_URL` | Sync Postgres connection string for Celery workers (`postgresql+psycopg2://...`) |
| `REDIS_URL` | Redis connection string (`redis://...`) |
| `SECRET_KEY` | JWT signing secret |
| `AWS_ACCESS_KEY_ID` | AWS key (use `test` for LocalStack) |
| `AWS_SECRET_ACCESS_KEY` | AWS secret (use `test` for LocalStack) |
| `AWS_REGION` | AWS region (e.g. `us-east-1`) |
| `S3_BUCKET` | S3 bucket name for photo uploads |
| `LOCALSTACK_URL` | LocalStack endpoint (e.g. `http://localstack:4566`) |
| `SENDER_EMAIL` | From address for SES emails |
| `FRONTEND_URL` | Base URL for email verification/reset links |

---

## Ports

| Service | Port |
|---|---|
| API | `http://localhost:8000` |
| API Docs | `http://localhost:8000/docs` |
| Postgres | `localhost:5432` |
| Redis | `localhost:6379` |
| LocalStack (AWS) | `http://localhost:4566` |

---

## Common commands

Most things have a Makefile shortcut:

```bash
make up              # start the stack
make down            # stop the stack
make shell           # open a shell inside the app container
make logs            # tail app logs

make migrate         # apply pending migrations
make migration msg="add column to users"   # generate a new migration
make downgrade       # roll back one migration
make reset           # wipe the DB and reapply all migrations (dev only)

make test            # run endpoint tests
make test-integration  # run integration tests (requires stack running)
make test-file file=tests/endpoint/test_auth.py
make test-one name=test_register_success

make seed            # seed with 25 realistic Austin users
make seed users=50   # seed with 50 users
make reseed          # wipe and reseed from scratch

make lint            # run ruff
make worker-logs     # tail Celery worker logs
make beat-logs       # tail Celery beat scheduler logs
make trigger-retention  # manually run the 90-day message purge task

make commit-lint msg="feat: add email verification"   # validate commit message locally
```

---

## Database migrations

Migrations are managed with Alembic. Always run them inside the container:

```bash
# Apply all pending migrations
make migrate

# Generate a new migration from model changes
make migration msg="your message here"

# Roll back one step
make downgrade
```

---

## Testing

Endpoint tests run against SQLite in-memory — no running stack needed:

```bash
make test
```

Integration tests hit the live Postgres + Redis stack, so the stack needs to be up:

```bash
make test-integration
```

Run a specific test by name across both suites:

```bash
make test-one name=test_login_success
```

---

## Seeding

The seed script creates realistic Austin-area test users with randomized bios, locations, and conversations:

```bash
make seed           # 25 users (default)
make seed users=50  # up to 50 users
make reseed         # reset DB first, then seed
```

Login with any seeded user using password `seedpassword123`.

---

## Celery workers

Two Celery containers run alongside the app:

- **celery-worker** — picks up photo moderation tasks queued by the upload endpoint
- **celery-beat** — runs scheduled tasks on a cron: message retention at 2am UTC, account hard-delete at 3am UTC

```bash
make worker-logs    # see what the worker is processing
make beat-logs      # see the scheduler firing tasks
make trigger-retention  # manually trigger the 90-day purge without waiting for 2am
```

---

## Commit messages

CI enforces a commit message format. Valid prefixes:

```
fix:    → bumps PATCH (0.0.1 → 0.0.2)
feat:   → bumps MINOR (0.1.0 → 0.2.0)
feat!:  → bumps MAJOR (1.0.0 → 2.0.0)
misc:   → no version bump
```

Validate locally before pushing:

```bash
make commit-lint msg="feat: add search endpoint"
```

---

## Project structure

```
findr/
├── app/
│   ├── api/routes/          # Route handlers
│   │   ├── auth.py          # Register, login, logout, email verification, password reset
│   │   ├── chats.py         # Group chat management
│   │   ├── legal.py         # Terms, location consent, reporting, CCPA export/delete
│   │   ├── location.py      # Update location, get nearby users, go offline
│   │   ├── messages.py      # Send, read, edit, delete messages
│   │   ├── photos.py        # Upload, delete, set primary, reorder photos
│   │   ├── search.py        # Username and bio keyword search
│   │   ├── user.py          # Profile get/update/delete
│   │   └── ws.py            # WebSocket map presence
│   ├── core/                # Shared logic
│   │   ├── email.py         # SES email helpers
│   │   ├── location.py      # Coordinate fuzzing, geohash, Haversine query
│   │   ├── presence.py      # Redis presence layer (set, remove, pub/sub)
│   │   ├── redis.py         # Redis singleton
│   │   ├── s3.py            # S3 and SES boto3 clients
│   │   ├── security.py      # JWT, password hashing, get_current_user
│   │   └── variables.py     # Env var loading
│   ├── models/models.py     # SQLAlchemy models
│   ├── schemas/schemas.py   # Pydantic schemas
│   ├── workers/             # Celery background tasks
│   │   ├── celery_app.py    # Celery config and beat schedule
│   │   ├── hard_delete.py   # Nightly PII anonymization (CCPA)
│   │   ├── moderation.py    # Rekognition photo moderation
│   │   └── retention.py     # 90-day message purge
│   ├── db.py                # SQLAlchemy engine and session
│   └── main.py              # FastAPI app entry point
├── migrations/              # Alembic migrations
├── scripts/
│   ├── localstack_init.sh   # Creates S3 bucket and SES identity on LocalStack startup
│   └── seed.py              # Test data seeder
├── tests/
│   ├── endpoint/            # Fast tests — SQLite in-memory, no stack needed
│   └── integration/         # Live tests — Postgres + Redis + LocalStack
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pytest.ini
└── requirements.txt
```