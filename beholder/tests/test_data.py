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
    ("2026-08-16T10:00:00+00:00", "Lanival", "Sorcery", 100, 10, 5),
    ("2026-08-16T10:00:00+00:00", "Lanival", "Evasion", 200, 20, 10),
    ("2026-08-16T10:01:00+00:00", "Lanival", "Sorcery", 100, 12, 7),
    ("2026-08-16T10:01:00+00:00", "Lanival", "Evasion", 200, 21, 9),
    ("2026-08-16T10:00:30+00:00", "Sable", "Athletics", 50, 5, 3),
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
    assert data.characters(connection) == ["Lanival", "Sable"]


def test_skills_are_per_character_and_sorted(connection):
    assert data.skills(connection, "Lanival") == ["Evasion", "Sorcery"]
    assert data.skills(connection, "Sable") == ["Athletics"]


def test_latest_snapshot_returns_only_the_newest_tick(connection):
    snapshot = data.latest_snapshot(connection, "Lanival")
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
    series = data.history(connection, "Lanival", ["Sorcery"])
    assert series == {
        "Sorcery": {
            "times": ["2026-08-16T10:00:00+00:00", "2026-08-16T10:01:00+00:00"],
            "mindstate": [5, 7],
            "rank": [100, 100],
        }
    }


def test_history_filters_to_requested_skills_and_character(connection):
    series = data.history(connection, "Lanival", ["Evasion", "Athletics"])
    assert list(series) == ["Evasion"]  # Athletics belongs to Sable


def test_history_without_skills_is_empty(connection):
    assert data.history(connection, "Lanival", []) == {}


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
    assert data.latest_character(connection) == "Lanival"


def test_history_since_windows_by_cutoff(connection):
    series = data.history_since(connection, "Lanival", "2026-08-16T10:00:30+00:00")
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
    circle INTEGER, tdps INTEGER, favors INTEGER, guild TEXT,
    rexp_stored INTEGER, rexp_usable INTEGER, rexp_refresh INTEGER
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
        " (logged_at, character_name, circle, tdps, favors, guild,"
        " rexp_stored, rexp_usable, rexp_refresh)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # 5:42 hours banked and usable at T1 (the captured footer,
            # #106); burnt out by T2, refreshing in 21 hours.
            (T1, "Lanival", 5, 300, 2, "Barbarian", 342, 342, 1260),
            (T2, "Lanival", 6, 320, 3, "Barbarian", 0, 0, 1260),
        ],
    )
    writer.executemany(
        "INSERT INTO stats (logged_at, character_name, stat, value)"
        " VALUES (?, ?, ?, ?)",
        [
            (T1, "Lanival", "Strength", 12),
            (T1, "Lanival", "Agility", 10),
            (T2, "Lanival", "Strength", 13),
            (T2, "Lanival", "Agility", 10),
            (T2, "Lanival", "Discipline", 11),
        ],
    )
    writer.executemany(
        "INSERT INTO sheet_skills"
        " (logged_at, character_name, skill_name, rank, percent)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (T1, "Lanival", "Evasion", 200, 20),
            (T1, "Lanival", "Sorcery", 100, 10),
            (T2, "Lanival", "Evasion", 200, 25),
            (T2, "Lanival", "Sorcery", 103, 50),
            (T2, "Lanival", "Athletics", 5, 0),
            (T1, "Newchar", "Larceny", 10, 5),
        ],
    )
    writer.commit()
    writer.close()
    connection = data.connect(path)
    yield connection
    connection.close()


def test_sheet_with_deltas_reports_gains_since_previous(sheet_connection):
    logged_at, rows = data.sheet_with_deltas(sheet_connection, "Lanival")
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
    logged_at, rows = data.stats_with_deltas(sheet_connection, "Lanival")
    assert logged_at == T2
    assert rows == [
        {"stat": "Agility", "value": 10, "gained": 0},
        {"stat": "Discipline", "value": 11, "gained": None},
        {"stat": "Strength", "value": 13, "gained": 1},
    ]


def test_sheet_history_charts_circle_tdps_favors(sheet_connection):
    history = data.sheet_history(sheet_connection, "Lanival")
    assert history == {
        "times": [T1, T2],
        "circle": [5, 6],
        "tdps": [300, 320],
        "favors": [2, 3],
    }


def test_stats_history_one_series_per_stat(sheet_connection):
    series = data.stats_history(sheet_connection, "Lanival")
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
            (T1, "Lanival", "carried", "Lirums", 5),
            (T2, "Lanival", "carried", "Lirums", 11),
            (T2, "Lanival", "carried", "Dokoras", 6),
            (T2, "Lanival", "debt", "Kronars", 90),
        ],
    )
    writer.commit()
    writer.close()

    logged_at, rows = data.wealth_current(sheet_connection, "Lanival")
    assert logged_at == T2
    assert rows == [
        {"kind": "carried", "currency": "Dokoras", "copper": 6},
        {"kind": "carried", "currency": "Lirums", "copper": 11},
        {"kind": "debt", "currency": "Kronars", "copper": 90},
    ]
    history = data.wealth_history(sheet_connection, "Lanival")
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
    assert data.latest_character(sheet_connection) == "Lanival"


# --- rested experience (#106) -------------------------------------------


def test_rexp_history_is_in_hours_oldest_first(sheet_connection):
    history = data.rexp_history(sheet_connection, "Lanival")
    assert history["times"] == [T1, T2]
    assert history["stored"] == [5.7, 0]
    assert history["usable"] == [5.7, 0]
    assert history["refresh"] == [21, 21]


def test_rexp_windows_open_at_a_snapshot_with_usable_hours(sheet_connection):
    # T1 had 5:42 usable; the next snapshot came 26 hours later, so the
    # window closes when the hours would have burnt out, not at T2.
    assert data.rexp_windows(sheet_connection, "Lanival") == [
        (T1, "2026-08-22T15:42:00+00:00")
    ]


def test_rexp_windows_close_at_the_next_snapshot_when_it_comes_first(tmp_path):
    import sqlite3

    path = tmp_path / "xp.db"
    writer = sqlite3.connect(path)
    writer.executescript(SHEET_TABLES)
    early, later = "2026-08-22T10:00:00+00:00", "2026-08-22T13:00:00+00:00"
    writer.executemany(
        "INSERT INTO character (logged_at, character_name, rexp_stored,"
        " rexp_usable, rexp_refresh) VALUES (?, ?, ?, ?, ?)",
        [(early, "Lanival", 342, 342, 1260), (later, "Lanival", 162, 162, 1080)],
    )
    writer.commit()
    writer.close()
    connection = data.connect(path)
    assert data.rexp_windows(connection, "Lanival") == [
        (early, later),
        (later, "2026-08-22T15:42:00+00:00"),
    ]
    connection.close()


def test_a_database_from_before_the_rexp_columns_yields_nothing(tmp_path):
    import sqlite3

    path = tmp_path / "xp.db"
    writer = sqlite3.connect(path)
    writer.executescript(
        "CREATE TABLE character (seq INTEGER PRIMARY KEY, logged_at TEXT,"
        " character_name TEXT, circle INTEGER, tdps INTEGER, favors INTEGER,"
        " guild TEXT);"
    )
    writer.execute(
        "INSERT INTO character (logged_at, character_name) VALUES (?, ?)",
        (T1, "Lanival"),
    )
    writer.commit()
    writer.close()
    connection = data.connect(path)
    assert data.rexp_history(connection, "Lanival")["times"] == []
    assert data.rexp_windows(connection, "Lanival") == []
    connection.close()


# --- spells (#136) ----------------------------------------------------------


def test_spells_come_from_the_newest_snapshot_with_the_slots(tmp_path):
    import sqlite3

    path = tmp_path / "xp.db"
    writer = sqlite3.connect(path)
    writer.executescript(
        SHEET_TABLES
        + """
        ALTER TABLE character ADD COLUMN spell_slots INTEGER;
        CREATE TABLE spells (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            logged_at TEXT NOT NULL, character_name TEXT NOT NULL,
            name TEXT NOT NULL, abbrev TEXT, kind TEXT NOT NULL, chapter TEXT
        );
        """
    )
    writer.executemany(
        "INSERT INTO character (logged_at, character_name, spell_slots)"
        " VALUES (?, ?, ?)",
        [(T1, "Lanival", 3), (T2, "Lanival", 2)],
    )
    writer.executemany(
        "INSERT INTO spells (logged_at, character_name, name, abbrev, kind, chapter)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            (T1, "Lanival", "Burden", None, "apprentice", None),
            (T2, "Lanival", "Heroic Strength", "hes", "learned", "Sacred Blade"),
            (T2, "Lanival", "Burden", None, "apprentice", None),
        ],
    )
    writer.commit()
    writer.close()
    connection = data.connect(path)
    known = data.spells(connection, "Lanival")
    assert known["slots"] == 2
    assert [row["name"] for row in known["rows"]] == ["Burden", "Heroic Strength"]
    assert data.spells(connection, "Nobody") == {"rows": [], "slots": None}
    connection.close()


def test_a_database_without_the_spells_table_yields_nothing(sheet_connection):
    assert data.spells(sheet_connection, "Lanival") == {"rows": [], "slots": None}
