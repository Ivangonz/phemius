# Contributing to Phemius

Thanks for helping. This guide covers how work is planned, how to set up a
development environment, and what a pull request needs before it merges.

## Development setup

You need [uv](https://docs.astral.sh/uv/getting-started/installation/), `git`,
`make` and, for the UI, [Node.js](https://nodejs.org) 22 with npm (pinned in
`frontend/.nvmrc`). uv installs Python 3.12 for the project.

```bash
git clone https://github.com/Ivangonz/phemius.git
cd phemius
make install     # uv sync --extra kokoro, then npm install in frontend/
make check       # backend and frontend checks
```

The Kokoro extra downloads about 300 MB on the first narration. Tests never need
it: they use the stub voice engine. See the [README](README.md) for running the
servers and the URLs to open.

Only UI work needs Node. Running Phemius never does, and backend contributors
can skip it:

```bash
make install backend   # uv only
make check backend     # ruff, ruff format check, mypy and pytest
```

### Make targets

Most targets take an optional second word, `backend` or `frontend`, to run only
that part. Without it they run both.

| Command | What it does |
| --- | --- |
| `make install` | `uv sync --extra kokoro` and `npm install` in `frontend/` |
| `make run` | API with reload on `http://127.0.0.1:8000` and the Vite dev server on `http://localhost:5173`, which proxies `/api` (`HOST` and `PORT` change the API only) |
| `make build` | Build the UI into `src/phemius/static` (not committed), which FastAPI serves |
| `make test` | `uv run pytest`, then `npm test` (Vitest) |
| `make lint` | `uv run ruff check .` and `uv run mypy`, then `npm run lint` and `npm run typecheck` |
| `make format` | `uv run ruff format .` and `uv run ruff check --fix .`, then `npm run format` (Prettier) |
| `make format-check` | `uv run ruff format --check .`, then `npm run format:check` |
| `make check` | `lint`, `format-check` and `test` for backend and frontend |
| `make api-types` | Export the OpenAPI schema to `frontend/openapi.json` and regenerate `frontend/src/lib/api-schema.d.ts` |
| `make help` | List the targets |

For example, `make test frontend` runs only the Vitest suite, `make lint backend`
only Ruff and mypy, and `make run backend` only the API.

### After changing the backend API

The UI's API types are generated from the FastAPI schema, never written by hand.
After you change a route, a request or response model, or a setting, run:

```bash
make api-types
```

and commit the updated `frontend/openapi.json` and
`frontend/src/lib/api-schema.d.ts` with your change. CI will check that they are
up to date once the frontend job lands (#42).

## Workflow

### 1. Start from an issue

All work starts from a GitHub issue. If there is none for what you want to do,
open one first with the bug or feature template so the scope is agreed before
code is written.

Issue titles use a scope prefix: `[backend]`, `[frontend]`, `[fullstack]`,
`[docs]` or `[infra]`.

### 2. Create a branch

Create the branch from the issue page ("Create a branch" in the Development
section), or name it yourself:

- `feature/{short-description}` for new behavior
- `fix/{short-description}` for bug fixes

Branch from `main`. Never commit directly to `main`; the branch rules below block
it.

### 3. Keep the change small

Each pull request does one thing completely and is reviewable in one sitting:
aim for under about 300 changed lines. A PR must not break anything if its
follow-up is delayed. If it grows, split it (for example the backend first, then
the UI) and open issues for the rest. Do not bundle unrelated changes; open a
separate issue for them.

### 4. Write tests first where it makes sense

Write the failing test, then the minimum code to pass it, then refactor.

- Test service logic, API endpoints (happy path, auth, invalid input), adapter
  error mapping, data integrity, migrations, and anything that filters or parses.
- Do not test framework internals, trivial getters or styling.
- **Tests never need network access, API keys, model downloads or ffmpeg.** The
  test setup in `tests/conftest.py` gives every test a fresh data folder, the stub
  voice engine and no model key. Use the `use_script_model` fixture with a fake
  model from `tests/models/fakes.py` where you need a script model.
- Backend tests mirror `src/phemius` under `tests/` and are named
  `test_{what_it_does}`.
- Changing the script prompt or how documents are prepared for it? Run the
  optional real-model evaluation described in
  [docs/script-evaluation.md](docs/script-evaluation.md).
- Frontend tests use Vitest, React Testing Library and MSW. Test what the user
  sees, and mock the API with MSW handlers rather than mocking `fetch`.

### 5. Run `make check` before pushing

```bash
make check
```

It runs the backend checks (`ruff check`, `ruff format --check`, `mypy` in
strict mode, `pytest`) and the frontend checks (ESLint, `tsc`, Prettier,
Vitest). That covers everything CI runs today. Fix the cause of a lint or type
error rather than silencing it with `# type: ignore`, `noqa` or `@ts-ignore`.

### 6. Open a pull request

- **Title:** `[scope] Imperative description`, using the same scopes as issues.
  For example: `[backend] Add Ollama adapter with installed-model detection`.
  Because `main` uses squash merges, the PR title becomes the commit message on
  `main`, so write it carefully.
- **Body:** fill in the
  [pull request template](.github/pull_request_template.md) (Summary, Changes,
  Testing, Notes) and end it with `Closes #N` for the issue it resolves.
- If the change affects what users see, include manual test steps: how to run
  it, what to do, what to expect, and edge cases such as empty input or a failing
  provider.

## Project board

Issues are tracked on the **Phemius** GitHub Project. The Status field moves as
follows:

| Status | How it gets there |
| --- | --- |
| Backlog | Automatically, when the issue is added to the project |
| In Progress | **By hand**, when you start working on the issue |
| In Review | Automatically, when a pull request with `Closes #N` links to the issue |
| Done | Automatically, when that pull request merges |

Only the In Progress step is manual, so remember to set it when you pick up an
issue. See [docs/project-board.md](docs/project-board.md) for how the board is
set up.

## Branch rules on `main`

A repository ruleset enforces these for everyone, including admins:

- Changes reach `main` only through a pull request.
- The `Backend` check (GitHub Actions workflow `CI`) must pass. It runs
  `ruff check`, `ruff format --check`, `mypy` and `pytest`, without the Kokoro
  extra.
- The branch must be up to date with `main` before it merges. If GitHub reports
  that it is behind, rebase it on `main` (or merge `main` into it) and let CI run
  again.
- Squash merge only. The squash commit uses the PR title.
- Linear history.
- No direct pushes, no force pushes, and the branch cannot be deleted.
- Merged branches are deleted automatically.

CI also runs two more jobs:

- **Frontend:** Node from `frontend/.nvmrc`, `npm ci`, a check that the API
  types are up to date (`make api-types` must leave no diff), then Prettier,
  ESLint, `tsc`, Vitest and the production build.
- **Package:** builds the UI, runs `uv build`, fails if the wheel or sdist lacks
  `phemius/static/index.html`, then installs the wheel in a clean virtualenv
  with no Node on `PATH` and requests `/` and `/api/health`.

## How the UI ships

Only UI contributors need Node. The React app is built into
`src/phemius/static`, which is ignored by git but listed as a hatchling build
artifact in `pyproject.toml`, so `uv build` puts it in the sdist and the wheel.
Anyone who installs the package gets the built UI and never runs Node.

To build a package locally, build the UI first; otherwise the package ships
without it and Phemius serves only the API:

```bash
make build   # npm ci first if frontend/node_modules is missing
uv build     # dist/phemius-<version>.tar.gz and .whl, with the UI inside
```

## Project conventions

[CLAUDE.md](CLAUDE.md) describes the product constraints and code conventions in
detail (it is also the context file for AI coding assistants). The ones that most
often come up in review:

- Routes are thin; business logic lives in `src/phemius/services/`.
- All SQL lives in `src/phemius/store/`.
- Provider-specific code lives only in `src/phemius/models/` and
  `src/phemius/voices/`.
- No network call inside a database transaction.
- Secrets are never logged, returned by the API or committed.
- Never truncate model output silently; raise an error with a hint.
- In the UI, every API call goes through `frontend/src/lib/api.ts`, and data
  fetching lives in hooks.

[docs/architecture.md](docs/architecture.md) explains the pipeline and records
architecture decisions. A change that reverses one of those decisions needs a new
ADR there.

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
