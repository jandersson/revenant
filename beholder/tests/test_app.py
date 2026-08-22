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
    figure = app.mindstate_figure(series, "Testchar")
    assert [trace.name for trace in figure.data] == ["Evasion", "Sorcery"]
    assert figure.data[1].y == (5,)
    assert "Testchar" in figure.layout.title.text


def test_mindstate_figure_without_history_is_an_empty_plot():
    figure = app.mindstate_figure({}, None)
    assert len(figure.data) == 0


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
        " rank, percent, mindstate) VALUES (?, 'Testchar', 'Athletics', 12, 1, 20)",
        (recent.isoformat(),),
    )
    writer.commit()
    writer.close()
    monkeypatch.setenv("REVENANT_XP_DB", str(path))


def test_dock_route_renders_the_recent_window(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    client = app.app.server.test_client()
    response = client.get("/dock?character=Testchar&hours=6")
    assert response.status_code == 200
    page_text = response.get_data(as_text=True)
    assert "Testchar" in page_text
    assert 'http-equiv="refresh"' in page_text


def test_dock_route_falls_back_to_the_latest_character(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    client = app.app.server.test_client()
    response = client.get("/dock")
    assert "Testchar" in response.get_data(as_text=True)


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
            " rank, percent) VALUES (?, 'Testchar', ?, ?, ?)",
            (logged_at, skill, rank, percent),
        )
    writer.execute(
        "INSERT INTO character (logged_at, character_name, circle, tdps,"
        " favors, guild) VALUES (?, 'Testchar', 1, 356, 0, ?)",
        (logged_at, guild),
    )
    writer.commit()
    writer.close()
    monkeypatch.setenv("REVENANT_XP_DB", str(path))


def test_circle_gates_reports_what_blocks_the_next_circle(monkeypatch, tmp_path):
    _seed_sheet(monkeypatch, tmp_path)
    rows, note = app.circle_gates("Testchar")
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
    rows, note = app.circle_gates("Testchar")
    assert rows == []
    assert ";sheet once" in note


def test_circle_gates_for_a_guild_without_circles(monkeypatch, tmp_path):
    _seed_sheet(monkeypatch, tmp_path, guild="Commoner")
    rows, note = app.circle_gates("Testchar")
    assert rows == []
    assert "No circle requirements" in note
