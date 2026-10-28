# Project board setup

Create a GitHub Project (Projects, New project, Board) named **Phemius** and link the `Ivangonz/phemius` repository.

## Fields

- **Status**: Backlog, Todo, In Progress, In Review, Done (matches the Rinnova workflow)
- **Priority**: single select, High / Medium / Low (mirrors the `priority:` labels)
- **Screen**: single select, S1 to S7 and C1 to C3 (mirrors the `screen:` labels)

## Workflow rules

- Turn on the built-in workflows: item added to project sets Status to Backlog; pull request opened sets Status to In Review; pull request merged sets Status to Done.
- Branch from `main` using the branch GitHub suggests on the issue ("Create a branch"). Never commit directly to `main`.
- PRs stay under about 300 lines. Split larger work into follow-up issues.
- PR titles use `[scope] Short description`, and the PR body ends with `Closes #N`.

## Views

- **Board**: group by Status.
- **By screen**: table grouped by Screen, to see what each UI concept still needs.
- **Roadmap**: optional, only if dates are ever added.
