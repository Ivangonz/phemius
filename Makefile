# Usage: make <command>
#   make install     Install dependencies, including Kokoro for real voices
#   make run         Run the dev server on http://127.0.0.1:8000
#   make check       Run everything CI runs

.PHONY: help install run test lint format format-check check

HOST ?= 127.0.0.1
PORT ?= 8000

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with uv, including the Kokoro voice engine
	uv sync --extra kokoro

run: ## Run the dev server with reload
	uv run uvicorn phemius.app:app --reload --host $(HOST) --port $(PORT)

test: ## Run the test suite
	uv run pytest

lint: ## Lint and type-check
	uv run ruff check .
	uv run mypy

format: ## Format code and apply safe lint fixes
	uv run ruff format .
	uv run ruff check --fix .

format-check: ## Check formatting without changing files
	uv run ruff format --check .

check: lint format-check test ## Run everything CI runs
