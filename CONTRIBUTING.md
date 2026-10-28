# Contributing to Phemius

Thanks for helping. This guide covers how work is planned, how to set up a
development environment, and what a pull request needs before it merges.

## Development setup

You need [uv](https://docs.astral.sh/uv/getting-started/installation/), `git` and
`make`. uv installs Python 3.12 for the project.

```bash
git clone https://github.com/Ivangonz/phemius.git
cd phemius
uv sync          # dependencies and dev tools, without Kokoro
make check       # everything CI runs
```

`uv sync` is enough for backend work and the tests. Run `make install` instead if
you want real narration from Kokoro (it adds the `kokoro` extra and downloads
about 300 MB on the first narration). See the [README](README.md) for running
the server.

Only contributors working on the UI need Node; running, testing and building the
Python package never do.

### Make targets

| Command | What it does |
| --- | --- |
| `make install` | `uv sync --extra kokoro`: dependencies plus the Kokoro voice engine |
| `make run` | Dev server with reload on `http://127.0.0.1:8000` (`HOST` and `PORT` override) |
| `make test` | `uv run pytest` |
| `make lint` | `uv run ruff check .` and `uv run mypy` |
| `make format` | `uv run ruff format .` and `uv run ruff check --fix .` |
| `make format-check` | `uv run ruff format --check .` |
| `make check` | `lint`, `format-check` and `test`: everything CI runs |
| `make help` | List the targets |

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
  voice engine and no model key. Use a fake script model where you need one.
- Tests mirror `src/phemius` under `tests/` and are named `test_{what_it_does}`.

### 5. Run `make check` before pushing

```bash
make check
```

It runs `ruff check`, `ruff format --check`, `mypy` (strict) and `pytest`, the
same checks CI runs. Fix the cause of a lint or type error rather than silencing
it with `# type: ignore` or `noqa`.

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
- Squash merge only. The squash commit uses the PR title.
- Linear history.
- No direct pushes, no force pushes, and the branch cannot be deleted.
- Merged branches are deleted automatically.

Required status checks are added once CI lands: the GitHub Actions workflow
`CI`, job `Backend`, which runs `ruff check`, `ruff format --check`, `mypy` and
`pytest`. Until then, run `make check` yourself before opening the PR.

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

[docs/architecture.md](docs/architecture.md) explains the pipeline and records
architecture decisions. A change that reverses one of those decisions needs a new
ADR there.

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
