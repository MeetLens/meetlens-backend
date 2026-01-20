# Repository Guidelines

## Project Structure & Module Organization
- `main.py` is the FastAPI entry point and wires REST + WebSocket routes.
- `endpoints/` holds HTTP/WebSocket handlers; keep request parsing here.
- `services/` contains business logic (LLM, transcription, summary workflows).
- `models/` defines Pydantic schemas and domain models used across routes.
- `database/` includes async SQLAlchemy setup and helpers; `alembic/` + `alembic.ini` manage migrations.
- `tests/` contains pytest suites; `docs/` holds product, API, and architecture references.
- `scripts/` provides helper tooling such as `scripts/setup_database.sh`.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` set up a local venv.
- `pip install -r requirements.txt` install Python dependencies.
- `fastapi dev main.py` run the development server at `http://localhost:8000`.
- `alembic upgrade head` apply database migrations.
- `pytest` run the full test suite.
- `pytest tests/test_database_schema.py tests/test_auth_flows.py -v` run focused DB tests.
- `scripts/setup_database.sh` create local `meetlens` and `meetlens_test` databases.

## Coding Style & Naming Conventions
- Python: 4-space indentation, PEP 8 alignment, and explicit imports.
- Naming: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Prefer type hints for new code and keep route handlers thin by delegating to `services/`.

## Testing Guidelines
- Frameworks: `pytest` with `pytest-asyncio` (see `pytest.ini` for discovery rules).
- Location and naming: tests live in `tests/` and follow `test_*.py` and `test_*` function naming.
- Add or update tests for new behavior, especially around async flows and external API boundaries.

## Commit & Pull Request Guidelines
- Commits use short, imperative summaries (e.g., "Add provider-specific configuration helper").
- PRs should include: a brief summary, testing notes (commands + results), and links to related issues.
- Call out schema, migration, or configuration changes explicitly, and update docs when behavior changes.

## AI Agent Guidelines
- **Documentation Retrieval**: Use the **Context7 MCP** (`use context7`) to fetch up-to-date documentation and code examples for libraries and APIs used in this project (e.g., FastAPI, SQLAlchemy, Alembic).

## Security & Configuration Tips
- Store secrets in `.env` (see `.env.example` for required keys); never commit real API keys.
- Use `DATABASE_URL` for local dev and `TEST_DATABASE_URL` for tests to avoid accidental data writes.
