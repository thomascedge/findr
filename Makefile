.PHONY: up down logs shell migrate migration downgrade reset lint test test-integration test-file test-one

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