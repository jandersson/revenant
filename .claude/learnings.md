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
- A fake script handle that advances a scripted timeline on every
  `sleep` gets its timeline eaten by inner waits the test didn't
  count (a stop-word grace sleeps once a second): hold the last state
  once the timeline is dry and end the run on a sleep budget instead
  (`test_train_script.py`'s Fake). Two ;train tests failed that way.
- Offscreen PyQt6 tests (`client/tests_gui`) can pass every test and
  still exit 139: anything that keeps a widget alive past the
  QApplication (a reader thread whose stub `read()` never raises
  EOFError, a widget left for shutdown GC) segfaults at interpreter
  exit on Linux and macOS, never on Windows. End every thread, join
  it, and `deleteLater()` plus a flush in the fixture teardown; the
  conftest's widget sweep exists for this.
- Moving a module a directory deeper breaks every `Path(__file__)
  .parents[n]` in it silently: the script engine's REPO_SCRIPTS_DIR
  pointed at `client/` instead of the repo after the engine/ move, and
  only its test noticed. Grep `__file__` in whatever moves.
- Parsed state lags the story line that announces the change: a
  failed climb's text arrives before the `<indicator>` that says the
  character is now sitting, so a script reacting to the text and
  reading the posture indicator at once sees the old posture (the
  walker's retry, 2026-09-11). Wait the roundtime out, or send the
  corrective command unconditionally when it is harmless (STAND).
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
  lines of Python — that is how `client/game/wounds_data.py` was generated.
- Elanthipedia item pages 404 under guessed names; shop pages
  (Tembeg's Armory) list items with coverage and price.
- The game's hand tags are separate elements, `<left ...>` and
  `<right ...>`, sent one at a time as each hand changes; a grep that
  requires both on one line sees only the login pair and reports
  "hands never changed". That misread a climb experiment twice on
  2026-09-11 (the items had been stowed). Grep each tag on its own,
  and give the parser `left_hand`/`right_hand` state (#159).

## Working with the operator

- Work on master in the main checkout, push after each change; no
  worktrees, no PRs. A message-wording change is a fix like any other:
  say what is happening, never two conditions hedged into one line.
- Every issue gets a label at creation; every defect found in passing
  gets an issue, not a fix inside an unrelated change.
- Live game actions on the operator's character need their say-so;
  reading logs and the history database never does.
