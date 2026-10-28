# Project board setup

Create a GitHub Project (Projects, New project, Board) named **Phemius** and link the `Ivangonz/phemius` repository.

## Fields

- **Status**: Backlog, In Progress, In Review, Done
- **Priority**: single select, High / Medium / Low (mirrors the `priority:` labels)
- **Screen**: single select, S1 to S7 and C1 to C3 (mirrors the `screen:` labels)

## Workflow rules

- Move an issue to In Progress by hand when you start it; no built-in workflow covers that step.
- Turn on the built-in workflows: item added to project sets Status to Backlog; pull request linked to issue (a `Closes #N` in the PR body) sets Status to In Review; pull request merged sets Status to Done.
- Branch from `main` using the branch GitHub suggests on the issue ("Create a branch"). Never commit directly to `main`.
- PRs stay under about 300 lines. Split larger work into follow-up issues.
- PR titles use `[scope] Short description`, and the PR body ends with `Closes #N`.

## Views

- **Board**: group by Status.
- **By screen**: table grouped by Screen, to see what each UI concept still needs.
- **Roadmap**: optional, only if dates are ever added.
