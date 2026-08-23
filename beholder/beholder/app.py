"""The beholder dashboard: skill experience history in the browser.

Plots mindstate and rank over time per character and skill, with a
sortable table of the latest learning queue — the historical companion
to the GUI's live Experience dock — and a Circle-gates table computing
what blocks the next circle from the latest ;sheet snapshot. Data
comes from the SQLite log the ;xp and ;sheet scripts write
(~/.revenant/xp.db; override REVENANT_XP_DB). Run with `uv run
beholder` and open http://127.0.0.1:8050.
"""

import argparse
import sqlite3

import plotly.graph_objects as go
from dash import Dash, Input, Output, dash_table, dcc, html

from beholder import data

# The circle-gates view computes with the client package's requirement
# tables; a standalone beholder install without it just hides the view.
try:
    from client import circles
except ImportError:  # pragma: no cover — the workspace always has it
    circles = None

REFRESH_MS = 60_000  # matches the ;xp snapshot interval

# Revenant's identity: dark surfaces and amber chrome, matching the GUI.
# Series colors are NOT the brand pastels — they are a categorical set
# validated for the dark surface (dataviz six checks: lightness band,
# chroma floor, CVD separation, normal-vision floor, contrast).
SURFACE = "#17171d"  # page and figure paper
PANEL = "#1e1e26"  # plot area, table chrome
GRID = "#2a2a34"
INK = "#c8c8d0"
MUTED = "#8a8a96"
ACCENT = "#d8b465"  # revenant amber: chrome only, never a series color
COLORWAY = [
    "#3987e5",
    "#d95926",
    "#199e70",
    "#c98500",
    "#d55181",
    "#008300",
    "#9085e9",
    "#e66767",
]

TABLE_STYLE = {
    "style_header": {
        "backgroundColor": PANEL,
        "color": ACCENT,
        "fontWeight": "bold",
        "border": f"1px solid {GRID}",
    },
    "style_data": {
        "backgroundColor": SURFACE,
        "color": INK,
        "border": f"1px solid {GRID}",
    },
    "style_filter": {"backgroundColor": PANEL, "color": INK},
    "style_cell": {
        "fontFamily": "ui-monospace, Menlo, Consolas, monospace",
        "fontSize": "13px",
        "textAlign": "left",
        "padding": "4px 8px",
    },
}


def themed(figure, title):
    """The shared chart chrome: dark surfaces, recessive grid, validated
    colorway. Specific figures set their own axes first; this merges."""
    figure.update_layout(
        title={"text": title, "font": {"color": INK, "size": 15}, "x": 0.02},
        paper_bgcolor=SURFACE,
        plot_bgcolor=PANEL,
        font={"color": INK},
        colorway=COLORWAY,
        xaxis={"gridcolor": GRID, "linecolor": GRID, "zerolinecolor": GRID},
        yaxis={"gridcolor": GRID, "linecolor": GRID, "zerolinecolor": GRID},
        margin={"l": 50, "r": 16, "t": 44, "b": 36},
    )
    return figure


TABLE_COLUMNS = [
    {"name": "Skill", "id": "skill_name"},
    {"name": "Rank", "id": "rank"},
    {"name": "Percent", "id": "percent"},
    {"name": "Mindstate", "id": "mindstate"},
]

STAT_COLUMNS = [
    {"name": "Stat", "id": "stat"},
    {"name": "Value", "id": "value"},
    {"name": "\u0394", "id": "gained"},
]

SHEET_COLUMNS = [
    {"name": "Skill", "id": "skill_name"},
    {"name": "Rank", "id": "rank"},
    {"name": "Percent", "id": "percent"},
    {"name": "\u0394 rank", "id": "gained"},
]

CIRCLE_COLUMNS = [
    {"name": "Set", "id": "category"},
    {"name": "Requirement", "id": "label"},
    {"name": "Skill", "id": "skill"},
    {"name": "Have", "id": "have"},
    {"name": "Need", "id": "need"},
]


def circle_gates(character):
    """Rows and note for the circle-gates view: what the guildleader
    would say gates the next circle, from the latest ;sheet snapshot."""
    if circles is None or not character:
        return [], ""
    snapshot = query(data.sheet_snapshot, character, default=None)
    if snapshot is None:
        return [], "No sheet snapshot yet — run ;sheet once in revenant."
    logged_at, circle, guild, ranks = snapshot
    if circle is None or guild is None:
        return [], "Snapshot predates circle/guild tracking — run ;sheet once."
    unmet = circles.gates(ranks, circle, guild)
    if unmet is None:
        return [], f"No circle requirements known for guild {guild}."
    note = (
        f"{guild}, circle {circle} → {circle + 1} — "
        f"from the sheet snapshot at {logged_at}"
    )
    if not unmet:
        return [], f"Nothing gates the next circle. {note}"
    rows = [dict(gate, skill=gate["skill"] or "—") for gate in unmet]
    return rows, note


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
        xaxis={
            "title": "Time (UTC)",
            "type": "date",
            "rangeslider": {"bgcolor": PANEL},
            "rangeselector": {
                "bgcolor": PANEL,
                "activecolor": GRID,
                "font": {"color": INK},
                "x": 1.0,
                "xanchor": "right",
                "y": 1.02,
                "yanchor": "bottom",
                "buttons": [
                    {"count": 1, "label": "1d", "step": "day", "stepmode": "backward"},
                    {"count": 3, "label": "3d", "step": "day", "stepmode": "backward"},
                    {"step": "all"},
                ],
            },
        },
        yaxis={"title": "Mindstate (0–34)", "range": [0, 34]},
    )
    return themed(
        figure,
        f"Mindstate over time — {character}" if character else "Mindstate over time",
    )


def series_figure(times, named_values, title, y_title):
    """One small single-axis chart (never dual-axis): one line per
    (name, values); a lone series shows no legend — the title names it."""
    figure = go.Figure()
    for name, values in named_values:
        figure.add_trace(
            go.Scatter(
                x=times,
                y=values,
                name=name,
                mode="lines+markers",
                line={"width": 2},
                marker={"size": 8},
            )
        )
    figure.update_layout(
        xaxis={"title": "", "type": "date"},
        yaxis={"title": y_title, "rangemode": "tozero"},
        showlegend=len(named_values) > 1,
        height=230,
    )
    return themed(figure, title)


def stats_figure(series, character):
    """Per-stat progression: one line per stat, shared axis."""
    figure = go.Figure()
    for stat in sorted(series):
        points = series[stat]
        figure.add_trace(
            go.Scatter(
                x=points["times"],
                y=points["values"],
                name=stat,
                mode="lines+markers",
                line={"width": 2},
                marker={"size": 8},
            )
        )
    figure.update_layout(
        xaxis={"title": "Time (UTC)", "type": "date"},
        yaxis={"title": "Stat value"},
        height=280,
    )
    return themed(
        figure, f"Stats over time — {character}" if character else "Stats over time"
    )


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
                **TABLE_STYLE,
            ),
            html.H3("Circle gates"),
            html.P(id="circle-note"),
            dash_table.DataTable(
                id="circle-table",
                columns=CIRCLE_COLUMNS,
                sort_action="native",
                **TABLE_STYLE,
            ),
            html.H3("Character sheet"),
            html.P(id="sheet-note", style={"color": MUTED}),
            html.Div(
                [
                    html.Div(
                        dash_table.DataTable(
                            id="stats-table",
                            columns=STAT_COLUMNS,
                            sort_action="native",
                            **TABLE_STYLE,
                        ),
                        style={"flex": "0 0 16rem"},
                    ),
                    html.Div(
                        [
                            dcc.Graph(id="circle-plot"),
                            dcc.Graph(id="tdp-plot"),
                        ],
                        style={"flex": "1", "minWidth": "0"},
                    ),
                ],
                style={"display": "flex", "gap": "1rem", "alignItems": "flex-start"},
            ),
            dcc.Graph(id="stats-plot"),
            html.H3("Full skill roster"),
            dash_table.DataTable(
                id="sheet-table",
                columns=SHEET_COLUMNS,
                sort_action="native",
                filter_action="native",
                **TABLE_STYLE,
            ),
            dcc.Interval(id="refresh", interval=REFRESH_MS),
        ],
        style={"maxWidth": "60rem", "margin": "0 auto", "fontFamily": "sans-serif"},
    )


def page(inner):
    """Pin the page to revenant's dark surface regardless of the
    browser's light/dark preference."""
    return html.Div(
        inner,
        style={
            "backgroundColor": SURFACE,
            "color": INK,
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
    Output("circle-table", "data"),
    Output("circle-note", "children"),
    Input("char-dropdown", "value"),
    Input("refresh", "n_intervals"),
)
def update_circle_gates(character, _tick):
    return circle_gates(character)


@app.callback(
    Output("sheet-note", "children"),
    Output("stats-table", "data"),
    Output("sheet-table", "data"),
    Output("circle-plot", "figure"),
    Output("tdp-plot", "figure"),
    Output("stats-plot", "figure"),
    Input("char-dropdown", "value"),
    Input("refresh", "n_intervals"),
)
def update_sheet(character, _tick):
    """The character-sheet view (#61): newest roster and stats with
    deltas since the previous ;sheet snapshot, and progression over
    time — circle & favors, TDPs, per-stat lines."""
    empty = (
        series_figure([], [], "Circle & favors", ""),
        series_figure([], [], "TDPs", ""),
        stats_figure({}, character),
    )
    if not character:
        return "", [], [], *empty
    sheet = query(data.sheet_with_deltas, character, default=None)
    if sheet is None:
        return (
            "No sheet snapshot yet — run ;sheet once in revenant.",
            [],
            [],
            *empty,
        )
    logged_at, roster = sheet
    stats_now = query(data.stats_with_deltas, character, default=None)
    header = query(data.sheet_snapshot, character, default=None)
    lead = ""
    if header and header[1] is not None:
        lead = f"{header[2]}, circle {header[1]} — "
    note = f"{lead}snapshot at {logged_at}; \u0394 is change since the previous one"
    progression = query(
        data.sheet_history,
        character,
        default={"times": [], "circle": [], "tdps": [], "favors": []},
    )
    stat_series = query(data.stats_history, character, default={})
    return (
        note,
        stats_now[1] if stats_now else [],
        roster,
        series_figure(
            progression["times"],
            [("Circle", progression["circle"]), ("Favors", progression["favors"])],
            "Circle & favors",
            "",
        ),
        series_figure(
            progression["times"], [("TDPs", progression["tdps"])], "TDPs", ""
        ),
        stats_figure(stat_series, character),
    )


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
