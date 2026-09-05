# Learnings for agents working on revenant

What tripped an agent up before, and the way that worked. Read once
per session; add a line when something new bites. Keep it to the
lessons the code and docs cannot carry themselves.

## Editing and tooling (Windows, Git Bash)

- Bulk edits go through a Python script written with the Write tool
  and run with `uv run python <file>`. A Python heredoc in Bash mangles
  backslash escapes (`\n` in old/new strings) and non-ASCII on the
  cp1252 stdin; several edits silently missed that way.
- Run `ruff format` before writing an edit script against a file you
  just created: the formatter re-wraps tuples and long lines, and an
  exact-match old string written from the unformatted text fails.
- `set -o pipefail` before `pytest ... | tail`, or a red suite commits
  green.
- Generated data modules get `# fmt: off` / `# fmt: on` around the
  literal so `ruff format --check` and the generator agree.
- Windows: a running session never sees edits to `client/` modules
  (xml_data, session, core) until the window is closed and relaunched;
  scripts and the reloadable helpers reach it through `;stop <name>`
  and running it again. Detach is not a restart.
- PowerShell `Stop-Process` kills what `taskkill` silently does not.

## Evidence first

- The game logs under `~/.revenant/logs/game-*.log` are the record of
  what the game said. Grep them before assuming a wording, and after
  every live run: the first `;hunt` (2026-09-05) exposed a kill line
  not in the table, a two-word corpse noun, and a `<crtrStatus>` with
  `dead="1"` that still said `hostile="1"` — three fixtures in one
  fight. Captured HEALTH answers were already in the logs when the
  wound parser was built.
- The session's debug log (`revenant_client-<stamp>-<pid>.log`) says
  which scripts started and when; the sessions registry says who is
  playing. Check both before asking the user what happened.
- WebFetch summarizes; it will not reproduce a large wiki table. Curl
  the page into the scratchpad and pull the tables out with a few
  lines of Python — that is how `client/wounds_data.py` was generated.
- Elanthipedia item pages 404 under guessed names; shop pages
  (Tembeg's Armory) list items with coverage and price.

## Working with the operator

- Work on master in the main checkout, push after each change; no
  worktrees, no PRs. A message-wording change is a fix like any other:
  say what is happening, never two conditions hedged into one line.
- Every issue gets a label at creation; every defect found in passing
  gets an issue, not a fix inside an unrelated change.
- Live game actions on the operator's character need their say-so;
  reading logs and the history database never does.
