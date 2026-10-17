"""How the dashboard shapes queries into the plot and table."""

from beholder import app


def _one_tick(*skills):
    return {
        skill: {
            "times": ["2026-08-16T10:00:00+00:00"],
            "mindstate": [5 + index],
            "rank": [100],
        }
        for index, skill in enumerate(skills)
    }


def test_each_skill_gets_its_own_strip_in_name_order():
    figure = app.mindstate_figure(_one_tick("Sorcery", "Evasion"), "Lanival")
    assert [trace.name for trace in figure.data] == ["Evasion", "Sorcery"]
    assert [trace.yaxis for trace in figure.data] == ["y", "y2"]
    assert figure.data[1].y == (5,)
    assert "Lanival" in figure.layout.title.text
    # Each strip is named at its right end, and every strip shares one
    # time axis, so a zoom in one moves them all.
    assert [note.text for note in figure.layout.annotations] == ["Evasion", "Sorcery"]
    assert figure.layout.xaxis.matches == "x2"


def test_a_skill_keeps_its_colour_whatever_else_is_selected():
    alone = app.mindstate_figure(_one_tick("Trading"), "Lanival")
    among = app.mindstate_figure(_one_tick("Arcana", "Trading", "Warding"), "Lanival")
    colour = {trace.name: trace.line.color for trace in among.data}
    assert alone.data[0].line.color == colour["Trading"] == app.skill_color("Trading")
    assert colour["Trading"] in app.COLORWAY


def test_the_strips_grow_the_plot_rather_than_squeezing_it():
    one = app.mindstate_figure(_one_tick("Trading"), "Lanival")
    ten = app.mindstate_figure(_one_tick(*"ABCDEFGHIJ"), "Lanival")
    assert ten.layout.height - one.layout.height == 9 * app.STRIP_HEIGHT


def test_the_skills_moving_chart_plots_the_count_against_the_skills_tracked():
    series = {
        "times": ["2026-09-26T21:00:00+00:00", "2026-09-26T21:01:00+00:00"],
        "moving": [20, 21],
        "tracked": [49, 49],
    }
    figure = app.moving_figure(series, "Lanival")
    assert figure.data[0].y == (20, 21)
    assert figure.layout.yaxis.range == (0, 49)
    assert "Skills moving — Lanival" in figure.layout.title.text
    empty = app.moving_figure({"times": [], "moving": [], "tracked": []}, None)
    assert empty.data[0].y == ()


def test_both_time_charts_open_on_the_last_three_days():
    # One tick from September beside today's training (#580's follow-up).
    times = ["2026-09-03T20:21:23+00:00", "2026-10-17T04:30:00+00:00"]
    moving = app.moving_figure(
        {"times": times, "moving": [1, 9], "tracked": [50, 50]}, "Lanival"
    )
    mindstate = app.mindstate_figure(
        {"Trading": {"times": times, "mindstate": [0, 13], "rank": [767, 768]}},
        "Lanival",
    )
    opening = ("2026-10-14T04:30:00+00:00", "2026-10-17T04:30:00+00:00")
    assert moving.layout.xaxis.range == opening
    assert mindstate.layout.xaxis.range == opening


def test_a_history_shorter_than_three_days_opens_whole():
    times = ["2026-10-16T22:00:00+00:00", "2026-10-17T04:30:00+00:00"]
    figure = app.moving_figure(
        {"times": times, "moving": [3, 1], "tracked": [10, 10]}, "Lanival"
    )
    assert figure.layout.xaxis.range == tuple(times)
    empty = app.moving_figure({"times": [], "moving": [], "tracked": []}, None)
    assert empty.layout.xaxis.range is None


def test_rested_windows_are_shaded_in_every_strip():
    windows = [("2026-08-22T10:00:00+00:00", "2026-08-22T15:42:00+00:00")]
    figure = app.mindstate_figure(_one_tick("Arcana", "Trading"), "Lanival", windows)
    shapes = figure.layout.shapes
    assert [shape.yref for shape in shapes] == ["y domain", "y2 domain"]
    assert all(
        shape.x0 == windows[0][0] and shape.x1 == windows[0][1] for shape in shapes
    )
    assert all(shape.fillcolor == app.REXP_SHADE for shape in shapes)
    # Named once in the legend, never per window: a label hung past a
    # four-minute window's hairline of shade.
    legend = [trace for trace in figure.data if trace.showlegend is not False]
    assert [trace.name for trace in legend] == ["Rested 3x"]
    assert legend[0].marker.color == app.REXP_SHADE


def test_rexp_figure_plots_stored_and_usable_hours():
    history = {
        "times": ["2026-08-22T10:00:00+00:00"],
        "stored": [5.7],
        "usable": [5.7],
        "refresh": [21],
    }
    figure = app.rexp_figure(history, "Lanival")
    assert [trace.name for trace in figure.data] == ["Stored", "Usable this cycle"]
    assert figure.data[0].y == (5.7,)
    assert "Rested experience" in figure.layout.title.text


def test_mindstate_figure_without_history_is_an_empty_plot():
    figure = app.mindstate_figure({}, None)
    assert len(figure.data) == 0


def _components(component):
    """Every component in a layout tree, depth-first."""
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    for child in children if isinstance(children, (list, tuple)) else [children]:
        if hasattr(child, "to_plotly_json"):
            yield from _components(child)


def test_the_tables_are_ag_grids_not_deprecated_datatables(monkeypatch, tmp_path):
    # dash_table.DataTable is deprecated upstream (#39): every table is
    # a dash-ag-grid now — sorting native, the learning queue and full
    # roster filterable — fed through rowData by the callbacks.
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "empty.db"))
    grids = {
        component.id: component
        for component in _components(app.serve_layout())
        if type(component).__name__ == "AgGrid"
    }
    assert set(grids) == {
        "exp-table",
        "circle-table",
        "stats-table",
        "wealth-table",
        "spells-table",
        "sheet-table",
    }
    exp_columns = grids["exp-table"].columnDefs
    assert [c["field"] for c in exp_columns] == [
        "skill_name",
        "rank",
        "percent",
        "mindstate",
    ]
    assert all(c["filter"] for c in exp_columns)  # the queue is filterable
    assert not any(c["filter"] for c in grids["stats-table"].columnDefs)
    callback_outputs = " ".join(app.app.callback_map)
    for table in grids:
        assert f"{table}.rowData" in callback_outputs


def test_query_returns_default_when_xp_has_never_run(monkeypatch, tmp_path):
    from beholder import data

    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "empty.db"))
    assert app.query(data.characters, default=[]) == []


def test_layout_hints_at_xp_when_there_is_no_history(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "empty.db"))
    layout = app.serve_layout()
    hints = [
        component.children
        for component in layout.children
        if getattr(component, "id", None) == "empty-hint"
    ]
    assert hints and ";xp" in hints[0]


def _seed(monkeypatch, tmp_path):
    import json  # noqa: F401 — parallel with test_data's writer fixture
    import sqlite3
    from datetime import datetime, timedelta, timezone

    path = tmp_path / "xp.db"
    writer = sqlite3.connect(path)
    writer.execute(
        "CREATE TABLE mindstate (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " logged_at TEXT NOT NULL, character_name TEXT NOT NULL,"
        " skill_name TEXT NOT NULL, rank INTEGER NOT NULL,"
        " percent INTEGER NOT NULL, mindstate INTEGER NOT NULL)"
    )
    recent = datetime.now(timezone.utc) - timedelta(minutes=30)
    writer.execute(
        "INSERT INTO mindstate (logged_at, character_name, skill_name,"
        " rank, percent, mindstate) VALUES (?, 'Lanival', 'Athletics', 12, 1, 20)",
        (recent.isoformat(),),
    )
    writer.commit()
    writer.close()
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(path))


def test_dock_route_renders_the_recent_window(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    client = app.app.server.test_client()
    response = client.get("/dock?character=Lanival&hours=6")
    assert response.status_code == 200
    page_text = response.get_data(as_text=True)
    assert "Lanival" in page_text
    assert 'http-equiv="refresh"' in page_text


def test_dock_route_falls_back_to_the_latest_character(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    client = app.app.server.test_client()
    response = client.get("/dock")
    assert "Lanival" in response.get_data(as_text=True)


def test_dock_route_survives_an_empty_database(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "missing.db"))
    client = app.app.server.test_client()
    response = client.get("/dock")
    assert response.status_code == 200
    assert "No recent history" in response.get_data(as_text=True)


def _seed_mindstate(monkeypatch, tmp_path, rows):
    import sqlite3

    path = tmp_path / "xp.db"
    writer = sqlite3.connect(path)
    writer.execute(
        "CREATE TABLE mindstate (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " logged_at TEXT NOT NULL, character_name TEXT NOT NULL,"
        " skill_name TEXT NOT NULL, rank INTEGER NOT NULL,"
        " percent INTEGER NOT NULL, mindstate INTEGER NOT NULL)"
    )
    writer.executemany(
        "INSERT INTO mindstate (logged_at, character_name, skill_name,"
        " rank, percent, mindstate) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    writer.commit()
    writer.close()
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(path))


def test_the_page_opens_on_the_most_recently_logged_character(monkeypatch, tmp_path):
    # Alvin sorts first but was last logged in August (#580).
    _seed_mindstate(
        monkeypatch,
        tmp_path,
        [
            ("2026-08-22T19:10:00+00:00", "Alvin", "Perception", 10, 1, 1),
            ("2026-10-17T04:30:00+00:00", "Lanival", "Trading", 768, 52, 13),
        ],
    )
    pickers = [
        component
        for component in app.serve_layout().children
        if getattr(component, "id", None) == "char-dropdown"
    ]
    assert pickers[0].options == ["Alvin", "Lanival"]
    assert pickers[0].value == "Lanival"


def test_the_skills_box_preselects_the_skills_that_learned(monkeypatch, tmp_path):
    _seed_mindstate(
        monkeypatch,
        tmp_path,
        [
            ("2026-10-17T04:00:00+00:00", "Lanival", "Trading", 768, 52, 13),
            ("2026-10-17T04:00:00+00:00", "Lanival", "Evasion", 200, 20, 0),
            ("2026-10-17T04:01:00+00:00", "Lanival", "Trading", 768, 53, 12),
            ("2026-10-17T04:01:00+00:00", "Lanival", "Evasion", 200, 20, 0),
        ],
    )
    options, chosen = app.update_skill_choices("Lanival")
    assert options == ["Evasion", "Trading"]
    assert chosen == ["Trading"]


def test_with_nothing_learning_the_skills_box_takes_the_latest_tick(
    monkeypatch, tmp_path
):
    _seed_mindstate(
        monkeypatch,
        tmp_path,
        [
            ("2026-10-17T04:00:00+00:00", "Lanival", "Trading", 768, 52, 0),
            ("2026-10-17T04:00:00+00:00", "Lanival", "Evasion", 200, 20, 0),
        ],
    )
    assert app.update_skill_choices("Lanival")[1] == ["Evasion", "Trading"]


def _seed_sheet(monkeypatch, tmp_path, guild="Thief"):
    import sqlite3

    path = tmp_path / "xp.db"
    writer = sqlite3.connect(path)
    writer.execute(
        "CREATE TABLE sheet_skills (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " logged_at TEXT NOT NULL, character_name TEXT NOT NULL,"
        " skill_name TEXT NOT NULL, rank INTEGER NOT NULL,"
        " percent INTEGER NOT NULL)"
    )
    writer.execute(
        "CREATE TABLE character (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " logged_at TEXT NOT NULL, character_name TEXT NOT NULL,"
        " circle INTEGER, tdps INTEGER, favors INTEGER, guild TEXT)"
    )
    logged_at = "2026-08-22T12:00:00+00:00"
    for skill, rank, percent in (
        ("Light Armor", 3, 48),
        ("Small Edged", 3, 0),
        ("Athletics", 22, 37),
    ):
        writer.execute(
            "INSERT INTO sheet_skills (logged_at, character_name, skill_name,"
            " rank, percent) VALUES (?, 'Lanival', ?, ?, ?)",
            (logged_at, skill, rank, percent),
        )
    writer.execute(
        "INSERT INTO character (logged_at, character_name, circle, tdps,"
        " favors, guild) VALUES (?, 'Lanival', 1, 356, 0, ?)",
        (logged_at, guild),
    )
    writer.commit()
    writer.close()
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(path))


def test_circle_gates_reports_what_blocks_the_next_circle(monkeypatch, tmp_path):
    _seed_sheet(monkeypatch, tmp_path)
    rows, note = app.circle_gates("Lanival")
    assert "Thief, circle 1 → 2" in note
    armor = next(row for row in rows if row["label"] == "1st Armor")
    assert armor == {
        "category": "armor",
        "label": "1st Armor",
        "skill": "Light Armor",
        "have": 3,
        "need": 4,
    }
    # An untrained slot renders a dash, not None.
    assert any(row["skill"] == "—" for row in rows)


def test_circle_gates_hint_at_sheet_without_a_snapshot(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "empty.db"))
    rows, note = app.circle_gates("Lanival")
    assert rows == []
    assert ";sheet once" in note


def test_circle_gates_for_a_guild_without_circles(monkeypatch, tmp_path):
    _seed_sheet(monkeypatch, tmp_path, guild="Commoner")
    rows, note = app.circle_gates("Lanival")
    assert rows == []
    assert "don't circle" in note  # a guild without circles, not an unknown one (#133)


# --- the identity line (#116) -------------------------------------------


def _row(**overrides):
    row = {
        "character_name": "Lanival",
        "race": "Human",
        "gender": "Male",
        "guild": "Barbarian",
        "circle": 6,
        "birth_year": 338,
        "birth_day": 29,
        "birth_month": 4,
    }
    row.update(overrides)
    return row


def test_the_identity_line_reads_as_a_sentence():
    line = app.describe_identity(_row())
    assert "Lanival" in line
    assert "Human" in line and "Male" in line and "Barbarian" in line
    assert "circle 6" in line
    assert "born 29/4 of 338" in line


def test_age_is_the_current_year_minus_the_birth_year():
    # Not stored anywhere: computed against the Elanthian calendar, so
    # it cannot go stale in the table (#115).
    from client.game import eltime

    now = 1788463232  # the captured observation instant
    current = eltime.elanthian_now(now).year
    line = app.describe_identity(_row(birth_year=338), now=now)
    assert f"age {current - 338}" in line


def test_an_unfinished_characters_year_zero_is_shown_not_hidden():
    # Birth year 0 is a real date: the character is as old as the
    # calendar, which is worth seeing rather than blanking.
    line = app.describe_identity(_row(birth_year=0, birth_day=1, birth_month=1))
    assert "born 1/1 of 0" in line
    assert "age " in line


def test_columns_the_snapshot_never_had_are_simply_left_out():
    # Rows written before the identity columns existed carry NULLs.
    line = app.describe_identity(
        _row(race=None, gender=None, birth_year=None, birth_day=None, birth_month=None)
    )
    assert line == "Lanival · Barbarian · circle 6"


def test_no_snapshot_means_no_line():
    assert app.describe_identity(None) == ""
    assert app.describe_identity({}) == ""
