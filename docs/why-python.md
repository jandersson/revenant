# Why revenant is pure Python (and what that costs)

Revenant replaces the lich/ProfanityFE Ruby toolchain with a pure-
Python stack, and the trade is deliberate: Python's library ecosystem
buys capabilities Ruby cannot match, at the price of walking away
from two decades of lich community work. This file records both sides
with the evidence, so the decision stays inspectable instead of
becoming folklore. The repo rule it anchors: revenant itself never
grows Ruby dependencies (CLAUDE.md).

## What Python buys — each claim shipped or demonstrated here

- **The data stack: pandas / plotly / Dash.** Beholder — the live
  experience dashboard embedded in the client — exists because these
  libraries do. Ruby's equivalents are abandoned (daru's last release
  predates this repo) and nothing like Dash exists at all. Lich users
  read text tables.
- **Graphs: networkx.** The community map is an 18,419-room,
  41,438-exit graph; it loads into networkx in six lines (measured
  2026-08-22, groundwork on #79) and brings weighted shortest paths,
  A*, articulation points, and centrality to routing. Ruby's `rgl`
  has been effectively unmaintained for a decade; lich's map code is
  hand-rolled BFS, and so is ours today — but only one of us has an
  upgrade path.
- **The scientific bench behind it**: scikit-learn and statsmodels
  for modeling training cadence from xp.db, torch for classifying
  game wordings (the ;mechlore unknown-message problem is a text
  classifier waiting to happen). No Ruby peer is within a decade of
  any of these.
- **Stdlib breadth.** The clocks dock (zoneinfo), the whole xp/sheet
  history pipeline (sqlite3), eltime (dataclasses), the session
  (threading, sockets) — substantial features with zero third-party
  dependencies.
- **Tooling.** uv workspaces with a lockfile, ruff, pytest: the
  entire CI is three fast tools, and a fresh clone is running in one
  command.
- **A native GUI.** PyQt6 is a maintained, first-class binding;
  Ruby's GUI story (Tk, dead GTK bindings) is why lich frontends are
  separate programs.

## What it costs — the fair column

- **Two decades of lich scripts.** Combat frameworks, hunting
  scripts, travel systems refined since the 2000s — all Ruby, none
  reusable. We re-pay that tuition in captures and corpses: the
  2026-08-22 cougar death (#72) taught ;athletics what lich scripts
  learned years ago.
- **The map's embedded Ruby.** Community map edges whose "command"
  is a Ruby proc (`;e ...`) are executable only by lich; we treat
  them as unwalkable, which genuinely severs some routes. (The
  unexplained cliffs↔Strand reachability gap in the #79 exploration
  may be exactly this.)
- **Interop tax with Ruby-shaped artifacts.** LNet speaks Ruby
  Marshal on the wire — the chat package carries a hand-written
  Marshal reader just to say hello. Payable (it works, it's tested),
  but a tax lich never pays.
- **No community to borrow from.** DR-scripting-in-Python has a
  population of one. Every wording, timer, and mechanic gets
  captured and pinned here first-hand (docs/eltime.md,
  docs/circles.md, docs/combat.md are what that looks like).
- **Terseness.** A lich one-liner is a revenant script with a
  docstring, a main(s), and tests. We count that as a feature — the
  tests are the manual — but it is more ceremony per script.

## The verdict the repo lives by

The cons are a fixed, one-time cost: re-learning mechanics and
re-writing frameworks, paid down capture by capture. The pros
compound: every new feature gets the ecosystem (beholder, the clocks
dock, #79's routing) rather than another hand-rolled corner. That
asymmetry is the bet.
