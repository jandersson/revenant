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
- Never chain a commit on `pytest ... | tail -1`: the Bash tool's shell
  ran a whole chain past "19 failed" on 2026-09-12 with `set -o
  pipefail` in front of it, and an issue got closed against a commit
  that never happened. Run pytest into a file, keep `$?` in a
  variable, print the tail, and gate the commit on the variable.
- A fake script handle that advances a scripted timeline on every
  `sleep` gets its timeline eaten by inner waits the test didn't
  count (a stop-word grace sleeps once a second): hold the last state
  once the timeline is dry and end the run on a sleep budget instead
  (`test_train_script.py`'s Fake). Two ;train tests failed that way.
- `QSettings("revenant", "revenant")` on Windows is the registry no
  matter what `QSettings.setDefaultFormat` / `setPath` say: the
  two-argument constructor ignores them, so the GUI suite's
  "isolated" settings wrote every run's synthetic Lanival layout into
  the real store until 2026-09-13, when a test's folded docks came
  back folded in a fresh window. The GUI reads the store through
  `client_gui.layout_settings()`, which the conftest points at an ini
  file with `REVENANT_QSETTINGS`; a test never constructs QSettings
  itself. Check the registry (`HKCU:\Software\revenant\revenant`)
  when a GUI test's state seems to outlive it.
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
  only its test noticed. Grep `__file__` in whatever moves. A running
  session whose helpers moved now says so once at the next script
  start ("restart the session", #155) instead of one raw error per
  module.
- Parsed state lags the story line that announces the change: a
  failed climb's text arrives before the `<indicator>` that says the
  character is now sitting, so a script reacting to the text and
  reading the posture indicator at once sees the old posture (the
  walker's retry, 2026-09-11). Wait the roundtime out, or send the
  corrective command unconditionally when it is harmless (STAND).
  The roundtime itself lags the send: it arrives with the prompt that
  closes the command's answer, so `waitrt()` straight after `put()`
  used to read the previous, spent roundtime and return at once
  (;athletics climbed one second into a two-second roundtime,
  2026-09-12). `Handle.waitrt` now waits for the command's own prompt
  (`XMLData.prompt_count`) before it trusts the roundtime.
- Generated data modules get `# fmt: off` / `# fmt: on` around the
  literal so `ruff format --check` and the generator agree.
- Windows: a running session never sees edits to `client/` modules
  (xml_data, session, core) until the window is closed and relaunched;
  scripts and the reloadable helpers reach it through `;stop <name>`
  and running it again. Detach is not a restart.
- PowerShell `Stop-Process` kills what `taskkill` silently does not.
- A bound-but-not-listening socket refuses a connection on Linux and
  Windows but not on macOS: XNU's tcp_input drops a SYN to a pcb still
  in CLOSED without a reset, so the connect times out. A test that
  wants a refusing port there must listen and close (the registry
  prune test failed on every macOS CI run for a day after #160 made a
  timeout mean "busy", 2026-09-12).

- A catalog merchant (the True Bard D'Or, Berolt's Dry Goods, Grek's)
  sells by haggling: ORDER <item> quotes ("I can let that go for...62
  kronars"), OFFER <amount> closes it, and a second ORDER or a BUY
  answers "We're still dealing" while a slow answer ends the deal. The
  session policy refuses an outside OFFER as a hand-over (#234) until
  `offer` is in `~/.revenant/policy/<name>.json`'s allow list — the
  operator added it for Cecil on 2026-09-20 after two stalled deals.
- A script that writes into the parser's state (`s.state.experience`
  and the like) writes the parser's whole shape: the engine renders
  every entry on every change with every key, and a `;scholarship`
  seed without a "rate" raised KeyError in the exp rewrite and ended
  the session at 04:30 on 2026-09-20 with `;train` running (#239).
  The renderer now reads with `.get` and the reader survives our own
  errors, but the rule stands: seed complete entries or none.
- A wet instrument (a river crossing, rain) refuses CLEAN until WIPEd
  with the cloth ("so wet that they are still dripping"); DRY is not a
  verb. CLEAN wants the instrument in hand (REMOVE a worn one).

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
- WebFetch summarizes; it will not reproduce a large wiki table. Read
  a wiki page through `uv run python tools/wiki.py "<Title>"` (raw
  wikitext, tables intact, cached under ~/.revenant/wiki so the
  second evening's read costs nothing and survives the site being
  down; `--grep WORD` for the lines that matter) and pull tables out
  with a few lines of Python — that is how `client/game/wounds_data.py`
  was generated. The operator asked for the cache on 2026-09-20 after
  a night of refetching the same soul and quest pages.
- Elanthipedia item pages 404 under guessed names; shop pages
  (Tembeg's Armory) list items with coverage and price.
- The engine feeds the parser one line at a time with the newline
  split off, so an accumulator that collects a multi-line window
  (the Spells window's pushStream) sees the lines glued together
  unless it puts the break back: two spells parsed as one until #175,
  and the parser test never caught it because it fed both lines in
  one string. Feed a fixture the way core.py does, line by line.
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
- A brand-new client/ module needs no session restart: the first
  script that imports it loads it from disk. RELOADABLE_MODULES and
  ;reexec matter only for edits to a module the session already
  holds (2026-09-12: ;tdp ran unrestarted; I had said otherwise).
- Patch files with a script written by the Write tool, not a Bash
  heredoc: the Bash tool unescapes backslashes on the way in, so a
  doubled backslash in a heredoc reaches Python as a single one and a
  test fixture's "\n" turns into a newline (three broken test files on
  2026-09-12 before this was pinned down).
- A module added to RELOADABLE_MODULES is reloadable only in sessions
  started after that edit: the list is engine code. A session that
  first imported the module before the list knew it keeps that first
  copy for good, and a script that later imports a new name from it
  fails to load ("cannot import name ...") until the session is
  restarted. Say so when landing a new game/ module (2026-09-12, tdp).
- Every command Claude sends into a session goes through revenant-send
  with `--origin claude`, so the window shows `>> [claude] ...`. The
  flag is the only thing that sets the tag; without it a line reads
  `[external]`, and the operator cannot tell who sent it (2026-09-12:
  a day of sends went out untagged).
- When walks or docks go quiet mid-session, replay the session's raw
  game log through the parser the way core.py feeds it (XMLParser
  per line, then route) and find the first line after which the
  signal stops; a line the game writes that XML forbids (a bare "&")
  broke the parser and every walk for the rest of a session before
  anyone looked (2026-09-12, #171).
- The game pushes every swing and kill line through `<pushStream
  id="combat"/>`, which the engine routes as its own stream: the main
  window shows it, but a handle's `get()` and anything reading the
  story alone never see it. Two hunts on 2026-09-12 ended "ground
  empty" among live rats before the raw log showed the tag before
  every kill line. When a script misses a line the window shows, look
  at the raw log for the pushStream around it before touching the
  wording tables.
- `;reexec` on Windows died twice with nothing to read (#162): the
  child is `pythonw`, which has no stderr, and it died before its
  logging started. Its stderr now lands in `~/.revenant/logs/reexec-
  <stamp>.err`, and a failed handoff no longer takes the old session
  down. Read that file before guessing at the cause.
- Never DROP. A script drops only through `client/game/discard.py`'s
  `drop()`, whose allowlist is the foraged junk ;mechlore braids
  (grass, grass rope) plus settings.json's `droppable`; anything else
  is refused with an echo. A hand is freed with `stow my <noun>` from
  the parser's `left_hand`/`right_hand` (athletics' `empty_hands`,
  hunt's `free_hand`); a load is lightened by stowing or banking
  coins. An advice line said "stow or drop the load" until the
  operator caught it (2026-09-12). Grep new echo text for "drop".
- Run the whole CI battery before every push — `ruff check`, `ruff
  format --check`, and all four suites (client/tests, client/tests_gui,
  beholder/tests, chat/tests), `tools/docker_tests.py` too when sockets
  or threads changed — not only the suite the change touched. A green
  remote run is meant to be expected (the operator, 2026-09-12, after
  a day of pushes checked against one suite each).
- A chain of `cmd | tail -1 && next` runs `next` on tail's exit code,
  not cmd's: a failed test suite committed and pushed that way once.
  `set -o pipefail` first, or check the summary line.
- A running script keeps the helper functions it imported by name,
  and a later reload of that helper module (another script starting
  after an edit) leaves those old functions running against the new
  module globals: `;hunt` held the walker's `walk` from before
  4c2a01c, `;circle` reloaded the walker, and the old `walk` died on
  the new three-value `await_arrival` ("too many values to unpack",
  2026-09-12, #181). A traceback's source lines are the current files,
  so its line numbers mislead; read the session log's "loaded ...
  (reloaded: [...])" lines around the crash instead. Since #181 a
  reload is a fresh module copy — running scripts keep the code they
  started with, the next start gets the new — and the log says which
  running scripts kept theirs.
