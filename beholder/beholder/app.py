"""The beholder dashboard: skill experience history in the browser.

Plots mindstate and rank over time per character and skill, with a
sortable table of the latest learning queue — the historical companion
to the GUI's live Experience dock. Data comes from the SQLite log the
;xp script writes (~/.revenant/xp.db; override REVENANT_XP_DB).
Run with `uv run beholder` and open http://127.0.0.1:8050.
"""

import argparse
import sqlite3

import plotly.graph_objects as go
from dash import Dash, Input, Output, dash_table, dcc, html

from beholder import data

REFRESH_MS = 60_000  # matches the ;xp snapshot interval

TABLE_COLUMNS = [
    {"name": "Skill", "id": "skill_name"},
    {"name": "Rank", "id": "rank"},
    {"name": "Percent", "id": "percent"},
    {"name": "Mindstate", "id": "mindstate"},
]


def query(fn, *args, default):
    """Run one data query on a fresh connection; `default` when the
    database is missing or has no mindstate table (;xp has never run)."""
    try:
        connection = data.connect()
    except sqlite3.OperationalError:
        return default
    try:
        return fn(connection, *args)
    except sqlite3.OperationalError:
        return default
    finally:
        connection.close()


def mindstate_figure(series, character):
    """One line per skill, mindstate over time, with 1d/3d/all range
    buttons and a range slider."""
    figure = go.Figure()
    for skill in sorted(series):
        points = series[skill]
        figure.add_trace(
            go.Scatter(
                x=points["times"],
                y=points["mindstate"],
                name=skill,
                mode="lines",
                hovertemplate="%{y} mindstate, rank %{customdata}<extra>%{fullData.name}</extra>",
                customdata=points["rank"],
            )
        )
    figure.update_layout(
        title=f"Mindstate over time — {character}"
        if character
        else "Mindstate over time",
        xaxis={
            "title": "Time (UTC)",
            "type": "date",
            "rangeslider": {},
            "rangeselector": {
                "buttons": [
                    {"count": 1, "label": "1d", "step": "day", "stepmode": "backward"},
                    {"count": 3, "label": "3d", "step": "day", "stepmode": "backward"},
                    {"step": "all"},
                ]
            },
        },
        yaxis={"title": "Mindstate (0–34)", "range": [0, 34]},
    )
    return figure


def serve_layout():
    """Built per page load, so a refresh sees new characters."""
    names = query(data.characters, default=[])
    character = names[0] if names else None
    hint = (
        ""
        if names
        else f"No history yet in {data.database_path()} — run ;xp in revenant first."
    )
    return html.Div(
        [
            html.H2("Beholder"),
            html.P(hint, id="empty-hint"),
            html.Label("Character"),
            dcc.Dropdown(id="char-dropdown", options=names, value=character),
            html.Label("Skills"),
            dcc.Dropdown(id="skills-dropdown", multi=True),
            dcc.Graph(id="mindstate-plot"),
            html.P(id="as-of"),
            dash_table.DataTable(
                id="exp-table",
                columns=TABLE_COLUMNS,
                sort_action="native",
                filter_action="native",
            ),
            dcc.Interval(id="refresh", interval=REFRESH_MS),
        ],
        style={"maxWidth": "60rem", "margin": "0 auto", "fontFamily": "sans-serif"},
    )


def page(inner):
    """Pin the page to a light background — browsers in dark mode
    otherwise paint the default body dark behind Plotly's light plot."""
    return html.Div(
        inner,
        style={
            "backgroundColor": "white",
            "color": "black",
            "minHeight": "100vh",
            "padding": "1rem",
        },
    )


app = Dash(__name__, title="Beholder")
app.layout = lambda: page(serve_layout())


def dock_figure(series, character):
    """The compact dock plot: one character's recent mindstate, chrome
    stripped and margins trimmed for a 300-500px dock (issue #59)."""
    import plotly.graph_objects as go_  # narrow alias keeps ruff quiet

    figure = go_.Figure()
    for skill in sorted(series):
        points = series[skill]
        figure.add_trace(
            go_.Scatter(
                x=points["times"], y=points["mindstate"], name=skill, mode="lines"
            )
        )
    figure.update_layout(
        title={"text": f"{character} — mindstate", "font": {"size": 13}},
        margin={"l": 30, "r": 8, "t": 34, "b": 22},
        paper_bgcolor="#17171d",
        plot_bgcolor="#1e1e26",
        font={"color": "#c8c8d0", "size": 10},
        yaxis={"range": [0, 34], "gridcolor": "#2a2a34"},
        xaxis={"gridcolor": "#2a2a34"},
        legend={"orientation": "h", "y": -0.15},
        showlegend=len(series) <= 8,
    )
    return figure


@app.server.route("/dock")
def dock():
    """The embeddable compact view: ?character=X&hours=6, both optional
    (latest-logged character, six hours). Self-refreshes every minute."""
    from datetime import datetime, timedelta, timezone

    import plotly.io
    from flask import request

    character = request.args.get("character")
    if not character:
        character = query(data.latest_character, default=None)
    try:
        hours = float(request.args.get("hours", 6))
    except ValueError:
        hours = 6.0
    body = None
    if character:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        series = query(data.history_since, character, since, default={})
        if series:
            body = plotly.io.to_html(
                dock_figure(series, character),
                include_plotlyjs=True,
                full_html=False,
                default_height="100vh",
            )
    if body is None:
        who = character or "anyone"
        body = (
            f"<p style='color:#8a8a96;font-family:sans-serif;padding:1rem'>"
            f"No recent history for {who} — climb something.</p>"
        )
    return (
        "<!DOCTYPE html><html><head>"
        '<meta http-equiv="refresh" content="60">'
        "<style>html,body{margin:0;background:#17171d;height:100%}</style>"
        f"</head><body>{body}</body></html>"
    )


@app.callback(
    Output("skills-dropdown", "options"),
    Output("skills-dropdown", "value"),
    Input("char-dropdown", "value"),
)
def update_skill_choices(character):
    """Offer every skill with history; preselect the current queue."""
    if not character:
        return [], []
    options = query(data.skills, character, default=[])
    latest = query(data.latest_snapshot, character, default=[])
    return options, [row["skill_name"] for row in latest]


@app.callback(
    Output("exp-table", "data"),
    Output("as-of", "children"),
    Input("char-dropdown", "value"),
    Input("refresh", "n_intervals"),
)
def update_table(character, _tick):
    if not character:
        return [], ""
    latest = query(data.latest_snapshot, character, default=[])
    as_of = f"as of {latest[0]['logged_at']}" if latest else ""
    return latest, as_of


@app.callback(
    Output("mindstate-plot", "figure"),
    Input("char-dropdown", "value"),
    Input("skills-dropdown", "value"),
    Input("refresh", "n_intervals"),
)
def update_plot(character, skill_names, _tick):
    if not character or not skill_names:
        return mindstate_figure({}, character)
    series = query(data.history, character, skill_names, default={})
    return mindstate_figure(series, character)


def main(argv=None):
    argparser = argparse.ArgumentParser(description=__doc__)
    argparser.add_argument("--host", default="127.0.0.1")
    argparser.add_argument("--port", type=int, default=8050)
    argparser.add_argument("--debug", action="store_true")
    args = argparser.parse_args(argv)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
