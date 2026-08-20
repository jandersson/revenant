# Beholder

A [Dash](https://dash.plotly.com/)/[Plotly](https://plotly.com/) web dashboard for DragonRealms character experience: mindstate and rank over time per character and per skill, with a sortable, filterable table of the latest learning queue. It is the historical companion to the client GUI's live Experience dock — the dock shows now, beholder shows the trend.

```
revenant client (xp script)  ──▶  ~/.revenant/xp.db  ──▶  beholder
```

1. The client's bundled xp script runs automatically in every session, snapshotting the exp window (rank / percent / mindstate per learning skill) into `~/.revenant/xp.db` every 60 seconds (override: `REVENANT_XP_DB`; opt out for a session with `;stop xp`, or permanently with `REVENANT_NO_XP=1`). See [scripts/xp.py](../scripts/xp.py).
2. Type `;beholder` in any frontend — it starts the dashboard if needed and opens <http://127.0.0.1:8050> in your browser. Or run it by hand:

```sh
uv run beholder                # options: --host, --port, --debug
```

The page auto-refreshes every 60 seconds to match the `;xp` cadence, and a browser refresh picks up newly logged characters.

## Layout

- **Character** — dropdown over every character with logged history.
- **Skills** — multi-select; preselects the character's current learning queue.
- **Mindstate plot** — one line per skill with 1d/3d/all range buttons and a range slider; hover shows mindstate and rank.
- **Experience table** — the latest snapshot per skill, sortable and filterable, with the snapshot timestamp above it.

## Development

Beholder is a member of the root uv workspace ([pyproject.toml](pyproject.toml)); its only runtime dependency is `dash`. The data layer ([beholder/data.py](beholder/data.py)) is stdlib `sqlite3` — each Dash callback opens a fresh connection, since callbacks run on worker threads. Tests live in [tests/](tests/):

```sh
uv run pytest beholder/tests -q
```

## History

The first beholder (2018) was fed by a lich script polling `DRSkill` inside the Ruby toolchain — first over redis, later straight into SQLite — and was built on Dash 0.22. This version replaces that pipeline with the pure-Python `;xp` script and modern Dash; the lich-era code (`revenant.lic`, the old `app.py`) lives on in git history.
