# Phemius: Claude Code Context

Read this before making changes, suggesting architecture or writing code.

## What We're Building

Phemius turns documentation into audio. It ingests documents (upload, watched folders, GitHub, Confluence, MCP), an AI agent categorizes each one and suggests a tone, rewrites it as a spoken script, and narrates it with a text-to-speech voice. Audio lives in a library you can play on a desktop or phone.

It is built for the owner's own use first, then released as an **open-source, self-hostable** tool. Users **bring their own models**: a hosted provider with an API key, any OpenAI-compatible server, or a local LLM such as Ollama. Voices are pluggable too (Kokoro by default, then Piper, OpenAI-compatible speech, ElevenLabs).

**One-sentence pitch:** Hear your docs.

## Who You Are

You are a Full Stack Software Engineer with decades of experience. You build products that are easy to maintain, easy to install and reliable, and you follow the best practices of each part of the stack.

## Product Constraints

- **Self-hosting is a feature.** A new user installs with one command (Docker or `uv tool install`) and hears audio within 10 minutes. Never add a runtime dependency (a second service, Node, a system library) without an issue that justifies it.
- **Nothing is hard-wired to one provider.** Script models and voice engines live behind adapters. No provider-specific code outside `phemius/models/` and `phemius/voices/`.
- **Works offline.** A fully local setup (Ollama + Kokoro or Piper) must keep working. Do not add features that require a network call to a Phemius-run service.
- **No user accounts.** One library, one optional access token. Anything reachable beyond localhost requires the token.
- **Secrets are write-only.** API keys and tokens are never returned by the API, never logged and never committed.

## Repository Structure

```
phemius/
├── src/phemius/
│   ├── app.py          # FastAPI app, route registration, static UI
│   ├── api/            # Routers, one per area (docs, audio, settings, sources, queue)
│   ├── services/       # Business logic callable from routes, jobs and the CLI
│   ├── models/         # Script model adapters (openrouter, openai_compatible, ollama)
│   ├── voices/         # Voice engine adapters (kokoro, piper, openai_speech, elevenlabs, stub)
│   ├── sources/        # Source connectors (folder, github, confluence)
│   ├── store/          # The only place that talks to SQLite
│   └── static/         # Built UI (generated, not committed)
├── frontend/           # React + Vite + TypeScript app (built into src/phemius/static)
├── tests/              # Mirrors src/phemius
├── docs/
│   ├── architecture.md # Architecture and decision log (ADRs)
│   └── project-board.md
├── Makefile
└── CLAUDE.md
```

This is the target layout. Some adapters, routers and connectors are added by later issues; check `src/phemius` for what exists today. The repository root also has `README.md`, `CONTRIBUTING.md` and `LICENSE` (Apache-2.0).

## Backend

**Language:** Python 3.12 (Kokoro supports only 3.10 to 3.12, so never raise the floor or ceiling without an ADR)
**Framework:** FastAPI + Pydantic v2
**Database:** SQLite (see ADR-001)
**Background work:** threads and a SQLite-backed job queue. No Celery, no Redis, no broker.
**Package manager:** `uv`

### Key Conventions

- Routes are thin: validate input, call a service function, return a response. Business logic lives in `services/`.
- **All SQL lives in `store/`.** No route, service or adapter writes queries. This keeps a future database swap contained.
- SQLite runs in **WAL mode** with a busy timeout. Keep write transactions short, and never call a network service (model provider, voice service, GitHub) inside a transaction.
- Any operation that writes to more than one table is wrapped in a single transaction.
- Adapters implement the `ScriptModel` / `VoiceEngine` / `Source` protocols. Adding one means adding one file and one registry line.
- Provider failures raise `ModelError` or `VoiceError` with `message` and `hint`. Never swallow them and never silently truncate output.
- Voice synthesis is serialized (one at a time); script writing may run in parallel. Jobs are idempotent and safe to retry.
- List endpoints are paginated with an explicit `order_by`. Default page size 25, max 100.
- Configuration precedence: environment variable, then saved setting, then default. Use the `PHEMIUS_*` prefix.
- Use `structlog` for logging. Log at service boundaries (API entry, external calls, job start and end). Never log secrets, document text or file contents; log IDs.
- Blocking work (TTS, file conversion, network calls to slow providers) never runs on the event loop. Use `async def` for I/O routes and push CPU-bound work to the job runner.

### API Error Response Format

Every error uses one shape so the frontend handles it uniformly:

```python
{
    "detail": "Model provider returned 402",
    "code": "model_error",
    "hint": "Add credits or lower the script length limit.",  # optional
    "errors": [  # optional, for validation errors
        {"field": "port", "message": "Must be between 1 and 65535"}
    ],
}
```

Register an explicit exception handler so custom errors (`ModelError`, `VoiceError`, validation) match this shape.

### Health Check

`GET /api/health` verifies the database is readable and the data folder is writable. Docker uses it for the container health check.

## Frontend

**Language:** TypeScript (strict)
**Build tool:** Vite
**Server state:** TanStack Query
**Routing:** TanStack Router (file-based)
**Styling:** Tailwind CSS, with components in `src/components/ui/` as owned source
**Tests:** Vitest + React Testing Library + MSW
**Delivery:** static files only, built in CI and bundled into the Python package and the Docker image. **No SSR, and no Node needed to run Phemius.**

- All API calls go through `src/lib/api.ts`. Never call `fetch` directly in components.
- API types are generated from the FastAPI OpenAPI schema with `openapi-typescript`. Do not hand-write them.
- Data fetching lives in custom hooks (`useDocuments`, `useSettings`). No `useQuery` inline in components.
- Every mutation invalidates the relevant queries.
- Forms use `react-hook-form` + `zod` when there are more than two fields.
- Every route has an `errorComponent`.
- Playback state (the player bar, C2) lives above the router so navigation never stops audio. Polling must not re-render a playing row.
- Components are `PascalCase`, hooks `useX`, handlers `handleX`, booleans `isX`/`hasX`/`canX`. Components stay under 150 lines; one component per file.
- Accessibility is required: semantic HTML, keyboard access, visible focus, 44px touch targets, labels on form fields, and status conveyed in text and never by color alone.
- UI follows the **Phemius UI concepts** (screens S1 to S7, components C1 to C3). Each issue names the screen it builds; match it at desktop and phone widths.

## Development Conventions

### Branching

**Never commit directly to `main`.** Create the branch from the GitHub issue ("Create a branch") or use `feature/{short-description}` / `fix/{short-description}`.

### Issues and Project Board

- Work comes from a GitHub issue. The PR body ends with `Closes #N`.
- Status lives on the GitHub Project: In Progress when you start, In Review when the PR opens, Done when it merges. Before closing the last issue of an area, check whether work is missing and suggest new issues.
- Issue titles use a scope prefix: `[backend]`, `[frontend]`, `[fullstack]`, `[docs]`, `[infra]`.

### Task Scoping and PR Size

Each task does one thing completely. A PR should be reviewable in one sitting (aim for under about 300 lines changed) and must not break anything if the follow-up is delayed. If a PR grows, split it (backend first, UI next). Never bundle unrelated changes; note them and open a separate issue.

### Test-Driven Development

Write the failing test first where it makes sense, then the minimum code, then refactor. Test for confidence, not coverage.

**Test:** service logic, API endpoints (happy path, auth, invalid input), adapter error mapping, data integrity, migrations, anything with filtering or parsing.
**Do not test:** framework internals, trivial getters, styling.

- Backend: `pytest` with `pytest-asyncio` (`asyncio_mode = "auto"`), `factory-boy` for data, `freezegun` for time, `httpx` for the test client. Tests mirror `src/phemius` under `tests/`. Name tests `test_{what_it_does}`.
- **Tests never need network, API keys, model downloads or ffmpeg.** Use the stub voice engine and a fake script model. Tests that need ffmpeg or a real model are marked and skipped in CI.
- Frontend: Vitest + React Testing Library + MSW. Test behavior the user sees; never mock `fetch` directly.

### Python Best Practices

- Type hints on every function signature. Use `X | None`, never `Optional[X]`. Use `type` statements (PEP 695) for repeated domain types. Use `Literal` for small constrained strings and `Callable` from `collections.abc` for callbacks.
- Naming: `snake_case` functions and variables, `PascalCase` classes, `UPPER_SNAKE_CASE` constants, booleans prefixed `is_`/`has_`/`can_`. No abbreviations and no single-letter names outside comprehensions.
- One function, one responsibility; aim for under 20 lines. If a function needs a comment to explain what it does, rename it.
- Imports grouped stdlib, third-party, local. No wildcard imports.
- **No `# type: ignore` or `noqa` to silence errors.** Fix the cause. The only exceptions are untyped third-party libraries and genuine stub mismatches: use a specific error code on a specific line, with a comment explaining why. More than 2 or 3 suppressions in one file means rethink the structure. Never add blanket `disable_error_code` overrides.

### Tooling (must match CI)

```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.12"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`make check` runs everything CI runs: `ruff check`, `ruff format --check`, `mypy`, `pytest`, and the frontend lint, typecheck, format check and tests.

### Code Review Checklist

**Backend**

- [ ] `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy .` pass
- [ ] Tests written first and passing, with no network, keys or model downloads
- [ ] Type hints on all signatures
- [ ] No SQL outside `store/`; no provider-specific code outside `models/` and `voices/`
- [ ] No network call inside a database transaction
- [ ] Migrations are safe and run on an existing library
- [ ] Secrets are write-only and absent from logs and API responses
- [ ] List endpoints paginated with an explicit order
- [ ] Jobs are idempotent and retry-safe

**Frontend**

- [ ] `npm run lint`, `npm run typecheck`, `npm run format:check` and `npm test` pass
- [ ] No `any`, no `@ts-ignore`, no commented-out code
- [ ] Data fetching in hooks; mutations invalidate queries
- [ ] Generated API types are up to date
- [ ] Matches the named screen at desktop and phone widths
- [ ] Keyboard accessible, status not conveyed by color alone

### Manual Testing Summary

After a task that changes user-facing behavior, end your message with **What to test manually**: prerequisites (`make run`), concrete steps, expected results and edge cases (empty input, a failing provider, missing ffmpeg).

### Pull Request Description

Use the repository PR template. After every completed task generate a ready-to-open description with these sections: Summary, Changes (Backend and Frontend), Testing (what was tested and how to test manually) and Notes.

**PR title format:** `[scope] short description in imperative mood`, for example `[backend] Add Ollama adapter with installed-model detection`.

## Things Not To Do

- Do not add a database server, message broker or other service to the default install. Revisit SQLite only through an ADR (see `docs/architecture.md`).
- Do not hard-wire a model provider or a voice engine outside its adapter.
- Do not add user accounts or telemetry.
- Do not add SSR, or a Node requirement at runtime.
- Do not add a second database backend unless an ADR approves it.
- Do not return or log secrets.
- Do not silently truncate model output; raise an error with a hint.
