# Beholder

A [Dash](https://plotly.com/dash/)/[Plotly](https://plotly.com/) web dashboard for DragonRealms character data. It plots mindstate / experience over time per character and per skill, with a refreshing data table, all fed by a lich script that polls `DRSkill` every minute and writes rows into SQLite.

> **Heads up:** this was a fun project but it hasn't been run in years. The pinned dependencies in [requirements.txt](requirements.txt) are old (Dash 0.22, Flask 1.0, pandas 0.23) and the Dash API has moved on significantly since. Expect to do some porting work before it runs cleanly. It's still a reasonable proof-of-concept if you want to build your own DR dashboard.

## How it works

```
lich + dr-scripts  ──▶  revenant.lic  ──▶  SQLite (MINDSTATE_R)  ──▶  SQLAlchemy  ──▶  Dash app
```

1. [revenant.lic](revenant.lic) runs inside lich. Every 60 seconds it walks `DRSkill.list` and inserts a row per skill into a `MINDSTATE_R` table (skill name, character, rank, mindstate, timestamp).
2. [app.py](app.py) opens that SQLite file through SQLAlchemy, pulls the latest snapshot for a selected character, and renders:
   - a character dropdown (distinct `character_name`s in the table),
   - a multi-select skills dropdown,
   - a time-series plot of mindstate per selected skill with a range slider and 1d/3d/all buttons,
   - an experience table that refreshes on a `dcc.Interval` tick.

The SQLite path is currently hard-coded in [app.py](app.py):

```py
engine = create_engine("sqlite:////home/jonas/lich/lich/data/revenant.db3")
```

You'll want to edit that for your own machine.

## Setup

### 1. Python environment

Pick your poison. The original requirements were pinned against Python 3.6:

```sh
# venv
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# or conda
conda create -n revenant python=3.6
conda activate revenant
```

Then:

```sh
pip install -r requirements.txt
```

If pip struggles with the ancient pins, consider relaxing them and porting to a modern Dash release — the app itself is small.

### 2. Install the data logger into lich

Assumes a working [lich](https://lichproject.org/) install alongside the [dr-scripts](https://github.com/rpherbig/dr-scripts) suite.

```sh
cp revenant.lic ~/lich/scripts/
```

Then, in game:

```
;revenant
;e autostart('revenant')   # optional, starts it every session
```

The script does not need to be trusted — it only uses `Script.db`, `DRSkill`, and `checkname`.

### 3. Run the app

```sh
python app.py
```

By default it listens on `0.0.0.0` with Dash's debug server.

## Files

- [app.py](app.py) — the Dash application and SQL queries
- [revenant.lic](revenant.lic) — the lich-side data logger
- [requirements.txt](requirements.txt) — (stale) pinned dependencies
