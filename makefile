.PHONY: up down test lint format shell

up:
	docker compose up -d

down:
	docker compose down

test:
	poetry run pytest tests/ -v

lint:
	poetry run ruff check src/

format:
	poetry run black src/ tests/

shell:
	poetry run ipython

logs:
	docker compose logs -f