# Usage: make <command> [backend|frontend]
#   make install         Install dependencies, including Kokoro for real voices
#   make run             Run the API on http://127.0.0.1:8000 and the UI dev server
#   make run frontend    Run only the Vite dev server (proxies /api to the API)
#   make test backend    Run only the backend tests
#   make check           Run everything CI runs

.PHONY: help install run build test lint format format-check check api-types backend frontend

HOST ?= 127.0.0.1
PORT ?= 8000

# The optional second word picks one app; it is swallowed so make doesn't run it.
APP := $(word 2, $(MAKECMDGOALS))

backend frontend:
	@true

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (uv with Kokoro, npm)
	@if [ "$(APP)" != "frontend" ]; then uv sync --extra kokoro; fi
	@if [ "$(APP)" != "backend" ]; then cd frontend && npm install; fi

run: ## Run the dev servers with reload
	@if [ "$(APP)" = "backend" ]; then \
		uv run uvicorn phemius.app:app --reload --host $(HOST) --port $(PORT); \
	elif [ "$(APP)" = "frontend" ]; then \
		cd frontend && npm run dev; \
	else \
		trap 'kill 0' INT TERM EXIT; \
		uv run uvicorn phemius.app:app --reload --host $(HOST) --port $(PORT) & \
		(cd frontend && npm run dev) & \
		wait; \
	fi

build: ## Build the UI into src/phemius/static
	cd frontend && npm run build

test: ## Run the test suites
	@if [ "$(APP)" != "frontend" ]; then uv run pytest; fi
	@if [ "$(APP)" != "backend" ]; then cd frontend && npm test; fi

lint: ## Lint and type-check
	@if [ "$(APP)" != "frontend" ]; then uv run ruff check . && uv run mypy; fi
	@if [ "$(APP)" != "backend" ]; then cd frontend && npm run lint && npm run typecheck; fi

format: ## Format code and apply safe lint fixes
	@if [ "$(APP)" != "frontend" ]; then uv run ruff format . && uv run ruff check --fix .; fi
	@if [ "$(APP)" != "backend" ]; then cd frontend && npm run format; fi

format-check: ## Check formatting without changing files
	@if [ "$(APP)" != "frontend" ]; then uv run ruff format --check .; fi
	@if [ "$(APP)" != "backend" ]; then cd frontend && npm run format:check; fi

check: lint format-check test ## Run everything CI runs

api-types: ## Export the OpenAPI schema and regenerate the UI's API types
	uv run python -m phemius.openapi frontend/openapi.json
	cd frontend && npm run generate:api-types
