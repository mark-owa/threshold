.PHONY: up down logs migrate revision seed seed-prompts seed-history test unit-test eval eval-live frontend-build lint

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f backend worker

migrate:
	docker compose exec backend alembic upgrade head

revision:
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

seed:
	docker compose exec backend python -m scripts.seed_demo_org

seed-prompts:
	docker compose exec backend python -m scripts.seed_prompts

seed-history:
	docker compose exec backend python -m scripts.seed_demo_history

eval:
	docker compose exec backend python -m scripts.evaluate_ai

eval-live:
	docker compose exec backend python -m scripts.evaluate_live_ai

frontend-build:
	cd frontend && npm ci && npm run build

test:
	docker compose exec backend pytest -v --cov=app --cov-report=term-missing

unit-test:
	PYTHONPATH=backend pytest -q backend/tests/unit --confcutdir=backend/tests/unit

lint:
	docker compose exec backend ruff check .
