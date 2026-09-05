"""How the dashboard shapes queries into the plot and table."""

from beholder import app


def test_mindstate_figure_has_one_sorted_trace_per_skill():
    series = {
        "Sorcery": {
            "times": ["2026-08-16T10:00:00+00:00"],
            "mindstate": [5],
            "rank": [100],
        },
        "Evasion": {
            "times": ["2026-08-16T10:00:00+00:00"],
            "mindstate": [10],
            "rank": [200],
        },
    }
    figure = app.mindstate_figure(series, "Lanival")
    assert [trace.name for trace in figure.data] == ["Evasion", "Sorcery"]
    assert figure.data[1].y == (5,)
    assert "Lanival" in figure.layout.title.text


def test_rested_windows_are_shaded_on_the_mindstate_plot():
    windows = [("2026-08-22T10:00:00+00:00", "2026-08-22T15:42:00+00:00")]
    figure = app.mindstate_figure({}, "Lanival", windows)
    shapes = figure.layout.shapes
    assert len(shapes) == 1
    assert shapes[0].x0 == windows[0][0] and shapes[0].x1 == windows[0][1]
    assert shapes[0].fillcolor == app.REXP_SHADE
    assert "rested 3x" in figure.layout.annotations[0].text


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
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "empty.db"))
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

    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "empty.db"))
    assert app.query(data.characters, default=[]) == []


def test_layout_hints_at_xp_when_there_is_no_history(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "empty.db"))
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
    monkeypatch.setenv("REVENANT_XP_DB", str(path))


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
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "missing.db"))
    client = app.app.server.test_client()
    response = client.get("/dock")
    assert response.status_code == 200
    assert "No recent history" in response.get_data(as_text=True)


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
    monkeypatch.setenv("REVENANT_XP_DB", str(path))


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
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "empty.db"))
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
    from client import eltime

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
