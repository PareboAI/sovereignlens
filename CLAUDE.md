# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SovereignLens is a sovereign AI intelligence platform. It scrapes and processes data, stores it in PostgreSQL (with Neo4j and Qdrant planned for Phase II), and exposes it via an API. The stack is Python 3.12 managed with Poetry.

## Commands

```bash
# Install dependencies
poetry install

# Run all tests
make test                          # poetry run pytest tests/ -v

# Run a single test file or test
poetry run pytest tests/unit/test_placeholder.py -v
poetry run pytest tests/ -v -k "test_name"

# Lint
make lint                          # poetry run ruff check src/

# Format
make format                        # poetry run black src/ tests/

# Start infrastructure (PostgreSQL)
make up                            # docker compose up -d

# Stop infrastructure
make down

# Follow logs
make logs

# Interactive shell
make shell                         # poetry run ipython
```

## Architecture

### Source layout (`src/`)

- **scraper/** — Scrapy-based web scrapers. Spiders live in `spiders/`, item definitions in `models/`, and data processing in `pipelines/`.
- **ai/** — AI/ML layer split into three sub-packages:
  - `agents/` — Autonomous agent logic (Anthropic API)
  - `extraction/` — Structured data extraction from raw content
  - `rag/` — Retrieval-augmented generation (future Qdrant integration)
- **graph/** — Knowledge graph layer (future Neo4j integration): schema definitions, data loaders, and query helpers.
- **api/** — HTTP API surface: `routes/` for endpoint handlers, `middleware/` for cross-cutting concerns.
- **frontend/** — Placeholder for the frontend layer.

### Infrastructure

| Service | Image | Port | Status |
|---------|-------|------|--------|
| PostgreSQL | postgres:16-alpine | 5432 | Active |
| Neo4j | neo4j:5.15 | 7474/7687 | Commented out (Phase II) |
| Qdrant | qdrant/qdrant | 6333 | Commented out (Phase II) |

### Environment variables (`.env`)

```
POSTGRES_URL=postgresql://sovereign:password@localhost:5432/sovereignlens
ANTHROPIC_API_KEY=
NEO4J_URI=
NEO4J_PASSWORD=
```

### Data flow

Scrapy spiders → pipelines → PostgreSQL (via SQLAlchemy/Alembic) → AI extraction/agents → graph layer → API routes → frontend

### Database migrations

Alembic is included for schema migrations. Migration files will live under the standard `alembic/` directory once initialized.

## Testing

Tests are split between `tests/unit/` and `tests/integration/`. The CI pipeline (`ruff` lint + `pytest`) runs on every push/PR to `main`.
