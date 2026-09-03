"""How beholder reads the ;xp history database."""

import pytest

from beholder import data

# Mirrors the schema scripts/xp.py creates.
SCHEMA = """
CREATE TABLE mindstate (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    rank INTEGER NOT NULL,
    percent INTEGER NOT NULL,
    mindstate INTEGER NOT NULL
)
"""

ROWS = [
    # (logged_at, character, skill, rank, percent, mindstate)
    ("2026-08-16T10:00:00+00:00", "Testchar", "Sorcery", 100, 10, 5),
    ("2026-08-16T10:00:00+00:00", "Testchar", "Evasion", 200, 20, 10),
    ("2026-08-16T10:01:00+00:00", "Testchar", "Sorcery", 100, 12, 7),
    ("2026-08-16T10:01:00+00:00", "Testchar", "Evasion", 200, 21, 9),
    ("2026-08-16T10:00:30+00:00", "Otherchar", "Athletics", 50, 5, 3),
]


@pytest.fixture
def connection(tmp_path):
    # Seed with a writer connection (data.connect is read-only by design).
    import sqlite3

    path = tmp_path / "xp.db"
    writer = sqlite3.connect(path)
    writer.execute(SCHEMA)
    writer.executemany(
        "INSERT INTO mindstate "
        "(logged_at, character_name, skill_name, rank, percent, mindstate) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ROWS,
    )
    writer.commit()
    writer.close()
    connection = data.connect(path)
    yield connection
    connection.close()


def test_characters_are_distinct_and_sorted(connection):
    assert data.characters(connection) == ["Otherchar", "Testchar"]


def test_skills_are_per_character_and_sorted(connection):
    assert data.skills(connection, "Testchar") == ["Evasion", "Sorcery"]
    assert data.skills(connection, "Otherchar") == ["Athletics"]


def test_latest_snapshot_returns_only_the_newest_tick(connection):
    snapshot = data.latest_snapshot(connection, "Testchar")
    assert [row["skill_name"] for row in snapshot] == ["Evasion", "Sorcery"]
    assert all(row["logged_at"] == "2026-08-16T10:01:00+00:00" for row in snapshot)
    assert snapshot[1] == {
        "skill_name": "Sorcery",
        "rank": 100,
        "percent": 12,
        "mindstate": 7,
        "logged_at": "2026-08-16T10:01:00+00:00",
    }


def test_history_is_per_skill_series_oldest_first(connection):
    series = data.history(connection, "Testchar", ["Sorcery"])
    assert series == {
        "Sorcery": {
            "times": ["2026-08-16T10:00:00+00:00", "2026-08-16T10:01:00+00:00"],
            "mindstate": [5, 7],
            "rank": [100, 100],
        }
    }


def test_history_filters_to_requested_skills_and_character(connection):
    series = data.history(connection, "Testchar", ["Evasion", "Athletics"])
    assert list(series) == ["Evasion"]  # Athletics belongs to Otherchar


def test_history_without_skills_is_empty(connection):
    assert data.history(connection, "Testchar", []) == {}


def test_unknown_character_yields_empty_results(connection):
    assert data.skills(connection, "Nobody") == []
    assert data.latest_snapshot(connection, "Nobody") == []
    assert data.history(connection, "Nobody", ["Sorcery"]) == {}


def test_database_path_honors_the_xp_scripts_override(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "elsewhere.db"))
    assert data.database_path() == tmp_path / "elsewhere.db"


def test_connect_is_read_only_and_never_creates_the_file(tmp_path):
    import sqlite3

    missing = tmp_path / "never-written.db"
    with pytest.raises(sqlite3.OperationalError):
        data.connect(missing)
    assert not missing.exists()  # the empty-xp.db side effect, regressed
    # And an existing database cannot be written through it.
    seeded = tmp_path / "seeded.db"
    writer = sqlite3.connect(seeded)
    writer.execute(SCHEMA)
    writer.commit()
    writer.close()
    reader = data.connect(seeded)
    with pytest.raises(sqlite3.OperationalError):
        reader.execute(
            "INSERT INTO mindstate (logged_at, character_name, skill_name, rank, percent, mindstate) VALUES ('t', 'c', 's', 1, 1, 1)"
        )
    reader.close()


def test_latest_character_is_the_most_recently_logged(connection):
    assert data.latest_character(connection) == "Testchar"


def test_history_since_windows_by_cutoff(connection):
    series = data.history_since(connection, "Testchar", "2026-08-16T10:00:30+00:00")
    assert series == {
        "Evasion": {
            "times": ["2026-08-16T10:01:00+00:00"],
            "mindstate": [9],
            "rank": [200],
        },
        "Sorcery": {
            "times": ["2026-08-16T10:01:00+00:00"],
            "mindstate": [7],
            "rank": [100],
        },
    }


# --- the character sheet: rosters, stats, and their histories -----------

SHEET_TABLES = """
CREATE TABLE character (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL, character_name TEXT NOT NULL,
    circle INTEGER, tdps INTEGER, favors INTEGER, guild TEXT
);
CREATE TABLE stats (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL, character_name TEXT NOT NULL,
    stat TEXT NOT NULL, value INTEGER NOT NULL
);
CREATE TABLE sheet_skills (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL, character_name TEXT NOT NULL,
    skill_name TEXT NOT NULL, rank INTEGER NOT NULL, percent INTEGER NOT NULL
);
"""

T1, T2 = "2026-08-22T10:00:00+00:00", "2026-08-23T12:00:00+00:00"


@pytest.fixture
def sheet_connection(tmp_path):
    import sqlite3

    path = tmp_path / "xp.db"
    writer = sqlite3.connect(path)
    writer.executescript(SHEET_TABLES)
    writer.executemany(
        "INSERT INTO character"
        " (logged_at, character_name, circle, tdps, favors, guild)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            (T1, "Testchar", 5, 300, 2, "Barbarian"),
            (T2, "Testchar", 6, 320, 3, "Barbarian"),
        ],
    )
    writer.executemany(
        "INSERT INTO stats (logged_at, character_name, stat, value)"
        " VALUES (?, ?, ?, ?)",
        [
            (T1, "Testchar", "Strength", 12),
            (T1, "Testchar", "Agility", 10),
            (T2, "Testchar", "Strength", 13),
            (T2, "Testchar", "Agility", 10),
            (T2, "Testchar", "Discipline", 11),
        ],
    )
    writer.executemany(
        "INSERT INTO sheet_skills"
        " (logged_at, character_name, skill_name, rank, percent)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (T1, "Testchar", "Evasion", 200, 20),
            (T1, "Testchar", "Sorcery", 100, 10),
            (T2, "Testchar", "Evasion", 200, 25),
            (T2, "Testchar", "Sorcery", 103, 50),
            (T2, "Testchar", "Athletics", 5, 0),
            (T1, "Newchar", "Larceny", 10, 5),
        ],
    )
    writer.commit()
    writer.close()
    connection = data.connect(path)
    yield connection
    connection.close()


def test_sheet_with_deltas_reports_gains_since_previous(sheet_connection):
    logged_at, rows = data.sheet_with_deltas(sheet_connection, "Testchar")
    assert logged_at == T2
    assert rows == [
        {"skill_name": "Athletics", "rank": 5, "percent": 0, "gained": None},
        {"skill_name": "Evasion", "rank": 200, "percent": 25, "gained": 0},
        {"skill_name": "Sorcery", "rank": 103, "percent": 50, "gained": 3},
    ]


def test_first_snapshot_has_no_deltas(sheet_connection):
    logged_at, rows = data.sheet_with_deltas(sheet_connection, "Newchar")
    assert rows == [{"skill_name": "Larceny", "rank": 10, "percent": 5, "gained": None}]


def test_no_snapshot_means_none(sheet_connection):
    assert data.sheet_with_deltas(sheet_connection, "Nobody") is None
    assert data.stats_with_deltas(sheet_connection, "Nobody") is None


def test_stats_with_deltas_tracks_purchases(sheet_connection):
    logged_at, rows = data.stats_with_deltas(sheet_connection, "Testchar")
    assert logged_at == T2
    assert rows == [
        {"stat": "Agility", "value": 10, "gained": 0},
        {"stat": "Discipline", "value": 11, "gained": None},
        {"stat": "Strength", "value": 13, "gained": 1},
    ]


def test_sheet_history_charts_circle_tdps_favors(sheet_connection):
    history = data.sheet_history(sheet_connection, "Testchar")
    assert history == {
        "times": [T1, T2],
        "circle": [5, 6],
        "tdps": [300, 320],
        "favors": [2, 3],
    }


def test_stats_history_one_series_per_stat(sheet_connection):
    series = data.stats_history(sheet_connection, "Testchar")
    assert series["Strength"] == {"times": [T1, T2], "values": [12, 13]}
    assert series["Discipline"] == {"times": [T2], "values": [11]}


def test_wealth_current_lists_coin_then_debt(sheet_connection):
    import sqlite3

    # wealth arrives with the same ;sheet snapshots
    writer = sqlite3.connect(
        sheet_connection.execute("PRAGMA database_list").fetchone()[2]
    )
    writer.executescript(
        "CREATE TABLE wealth (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " logged_at TEXT NOT NULL, character_name TEXT NOT NULL,"
        " kind TEXT NOT NULL, currency TEXT NOT NULL, copper INTEGER NOT NULL)"
    )
    writer.executemany(
        "INSERT INTO wealth (logged_at, character_name, kind, currency, copper)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (T1, "Testchar", "carried", "Lirums", 5),
            (T2, "Testchar", "carried", "Lirums", 11),
            (T2, "Testchar", "carried", "Dokoras", 6),
            (T2, "Testchar", "debt", "Kronars", 90),
        ],
    )
    writer.commit()
    writer.close()

    logged_at, rows = data.wealth_current(sheet_connection, "Testchar")
    assert logged_at == T2
    assert rows == [
        {"kind": "carried", "currency": "Dokoras", "copper": 6},
        {"kind": "carried", "currency": "Lirums", "copper": 11},
        {"kind": "debt", "currency": "Kronars", "copper": 90},
    ]
    history = data.wealth_history(sheet_connection, "Testchar")
    assert history["Lirums"] == {"times": [T1, T2], "values": [5, 11]}
    assert "Kronars" not in history  # debt never charts as coin


# --- the picker and the identity panel (#116) ---------------------------

IDENTITY_TABLES = """
CREATE TABLE mindstate (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL, character_name TEXT NOT NULL,
    skill_name TEXT NOT NULL, rank INTEGER NOT NULL,
    percent INTEGER NOT NULL, mindstate INTEGER NOT NULL
);
CREATE TABLE character (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL, character_name TEXT NOT NULL,
    circle INTEGER, tdps INTEGER, favors INTEGER, guild TEXT,
    race TEXT, gender TEXT,
    birth_year INTEGER, birth_day INTEGER, birth_month INTEGER
);
"""


@pytest.fixture
def identity_connection(tmp_path):
    import sqlite3

    path = tmp_path / "xp.db"
    writer = sqlite3.connect(path)
    writer.executescript(IDENTITY_TABLES)
    # Trained: has mindstate AND a sheet. Sweptonly: sheet only — the
    # case that used to vanish from the picker.
    writer.execute(
        "INSERT INTO mindstate"
        " (logged_at, character_name, skill_name, rank, percent, mindstate)"
        " VALUES ('2026-08-16T10:00:00+00:00', 'Trained', 'Sorcery', 10, 5, 3)"
    )
    writer.executemany(
        "INSERT INTO character (logged_at, character_name, circle, guild,"
        " race, gender, birth_year, birth_day, birth_month)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (T1, "Trained", 5, "Barbarian", "Human", "Male", 338, 29, 4),
            (T1, "Sweptonly", 90, "Trader", "Elothean", "Female", 395, 1, 2),
            # An unfinished character: birth year 0 is real, not missing.
            (T1, "Epochborn", 0, "Commoner", "Human", "Male", 0, 1, 1),
            (T2, "Trained", 6, "Barbarian", "Human", "Male", 338, 29, 4),
        ],
    )
    writer.commit()
    writer.close()
    connection = data.connect(path)
    yield connection
    connection.close()


def test_the_picker_lists_swept_characters_too(identity_connection):
    # The regression: only mindstate was listed, so a character that was
    # snapshotted but never trained could not be selected at all.
    assert data.characters(identity_connection) == [
        "Epochborn",
        "Sweptonly",
        "Trained",
    ]


def test_the_picker_does_not_repeat_a_character_in_both_tables(identity_connection):
    names = data.characters(identity_connection)
    assert len(names) == len(set(names))


def test_identity_reads_the_newest_snapshot(identity_connection):
    row = data.identity(identity_connection, "Trained")
    assert row["circle"] == 6  # T2, not T1
    assert (row["race"], row["gender"], row["guild"]) == ("Human", "Male", "Barbarian")
    assert (row["birth_year"], row["birth_day"], row["birth_month"]) == (338, 29, 4)


def test_identity_works_for_a_character_with_no_training_history(identity_connection):
    row = data.identity(identity_connection, "Sweptonly")
    assert row["race"] == "Elothean"
    assert row["circle"] == 90


def test_identity_of_an_unknown_character_is_none(identity_connection):
    assert data.identity(identity_connection, "Nobody") is None


def test_latest_character_falls_back_to_the_sheet(sheet_connection):
    # A swept database with no mindstate at all must still open on a
    # character rather than nothing.
    assert data.latest_character(sheet_connection) == "Testchar"
