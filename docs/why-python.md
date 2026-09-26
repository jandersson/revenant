# Why pure Python

Revenant replaces the Lich/ProfanityFE Ruby toolchain with Python on purpose: Python's libraries buy what Ruby cannot, at the cost of Lich's two decades of scripts. Revenant itself never grows Ruby dependencies; `launcher/` is the only bridge.

## What Python buys

- **Data:** pandas, plotly and Dash are why beholder exists. Ruby's equivalents are abandoned.
- **Graphs:** the community map (about 18,000 rooms) loads into networkx in a few lines, with weighted paths and centrality ready for routing.
- **Modeling:** scikit-learn, statsmodels and torch are there for training history or classifying game wordings.
- **Stdlib:** sqlite3, zoneinfo, threading and sockets carry whole features with no third-party code.
- **Tooling:** uv, ruff and pytest; a fresh clone runs in one command.
- **GUI:** PyQt6 is a maintained binding; Ruby's GUI gap is why Lich frontends are separate programs.

## What it costs

- **Lich's scripts.** Combat, hunting and travel frameworks refined for years — none reusable. We relearn their lessons one capture at a time.
- **The map's Ruby.** Map edges whose command is a Ruby proc only run under Lich; we treat them as unwalkable, which cuts some routes.
- **Ruby on the wire.** LNet answers in Ruby Marshal, so the chat package carries its own Marshal reader.
- **No community.** Every wording, timer and mechanic is captured here first-hand.
- **Ceremony.** A Lich one-liner is a revenant script with a docstring, `main(s)` and tests.

## The bet

The costs are paid once, capture by capture. The gains compound: every new feature gets the ecosystem instead of another hand-rolled corner.
