.PHONY: up down logs shell migrate migration downgrade reset lint test test-integration test-file test-one worker-logs beat-logs trigger-retention

# ── Docker ────────────────────────────────────────────────────────────────────

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f app

shell:
	docker compose exec app bash

# ── Database ──────────────────────────────────────────────────────────────────

# Apply all pending migrations
migrate:
	docker compose exec app alembic upgrade head

# Generate a new migration from model changes
# Usage: make migration msg="add column to users"
migration:
	@test -n "$(msg)" || (echo "Usage: make migration msg='your message'"; exit 1)
	docker compose exec app alembic revision --autogenerate -m "$(msg)"

# Roll back one migration
downgrade:
	docker compose exec app alembic downgrade -1

# Wipe and recreate the database from scratch — dev only
reset:
	docker compose exec db psql -U postgres -d findr -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	docker compose exec app alembic upgrade head

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	docker compose exec app pytest tests/endpoint/ -v

test-integration:
	docker compose exec app pytest tests/integration/ -v

# Run a single test file
# Usage: make test-file file=tests/test_auth.py
test-file:
	@test -n "$(file)" || (echo "Usage: make test-file file=tests/test_auth.py"; exit 1)
	docker compose exec app pytest $(file) -v

# Run a single test by name
# Usage: make test-one name=test_register_success
test-one:
	@test -n "$(name)" || (echo "Usage: make test-one name=test_register_success"; exit 1)
	docker compose exec app pytest tests/endpoint/ tests/integration/ -v -k $(name)

# ── Code quality ──────────────────────────────────────────────────────────────

lint:
	docker compose exec app ruff check app/

# ── Celery ────────────────────────────────────────────────────────────────────

# Follow worker logs
worker-logs:
	docker compose logs -f celery-worker

# Follow beat scheduler logs
beat-logs:
	docker compose logs -f celery-beat

# Manually trigger the retention task without waiting for 2am
trigger-retention:
	docker compose exec app python -c "from app.workers.retention import purge_old_messages; purge_old_messages.delay()"

# ── Seeding ──────────────────────────────────────────────────────────────────
 
# Seed the database with realistic Austin test data
# Usage: make seed
# Usage: make seed users=50
seed:
	docker compose exec app python scripts/seed.py --users $(or $(users),25)
 
# Wipe and reseed from scratch
reseed:
	make reset
	sleep 3
	make seed
 
 # ── Git ───────────────────────────────────────────────────────────────────────
 
# Validate your commit message locally before pushing
# Usage: make commit msg="feat: add email verification"
commit-lint:
	@echo "$(msg)" | grep -qE "^(fix|feat|feat!|misc):" \
		&& echo "✅ Valid commit message" \
		|| (echo "❌ Invalid: must start with fix:, feat:, feat!:, or misc:" && exit 1)