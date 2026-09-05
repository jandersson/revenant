"""Where the history database lives, and how xp.db becomes history.db
— the manual (#121).

The env var wins (new spelling, then the old); without one the default
is ~/.revenant/history.db, and an existing xp.db there is moved into
place once, journal included, never copied and never lost.
"""

from client import history


def test_the_override_wins_in_either_spelling(monkeypatch, tmp_path):
    monkeypatch.delenv(history.LEGACY_ENV, raising=False)
    monkeypatch.setenv(history.ENV, str(tmp_path / "mine.db"))
    assert history.database_path() == tmp_path / "mine.db"
    monkeypatch.delenv(history.ENV)
    monkeypatch.setenv(history.LEGACY_ENV, str(tmp_path / "old-spelling.db"))
    assert history.database_path() == tmp_path / "old-spelling.db"


def test_a_legacy_xp_db_is_moved_to_history_db_once(monkeypatch, tmp_path):
    monkeypatch.delenv(history.ENV, raising=False)
    monkeypatch.delenv(history.LEGACY_ENV, raising=False)
    monkeypatch.setattr(history, "DEFAULT_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(history, "LEGACY_PATH", str(tmp_path / "xp.db"))
    (tmp_path / "xp.db").write_bytes(b"the whole history")
    (tmp_path / "xp.db-journal").write_bytes(b"pending")
    assert history.database_path() == tmp_path / "history.db"
    assert (tmp_path / "history.db").read_bytes() == b"the whole history"
    assert (tmp_path / "history.db-journal").read_bytes() == b"pending"
    assert not (tmp_path / "xp.db").exists()
    assert not (tmp_path / "xp.db-journal").exists()


def test_an_existing_history_db_is_left_alone(monkeypatch, tmp_path):
    monkeypatch.delenv(history.ENV, raising=False)
    monkeypatch.delenv(history.LEGACY_ENV, raising=False)
    monkeypatch.setattr(history, "DEFAULT_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(history, "LEGACY_PATH", str(tmp_path / "xp.db"))
    (tmp_path / "history.db").write_bytes(b"current")
    (tmp_path / "xp.db").write_bytes(b"stale copy")
    assert history.database_path() == tmp_path / "history.db"
    assert (tmp_path / "history.db").read_bytes() == b"current"
    assert (tmp_path / "xp.db").exists()  # nothing is deleted behind the user's back


def test_no_database_at_all_just_names_the_new_path(monkeypatch, tmp_path):
    monkeypatch.delenv(history.ENV, raising=False)
    monkeypatch.delenv(history.LEGACY_ENV, raising=False)
    monkeypatch.setattr(history, "DEFAULT_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(history, "LEGACY_PATH", str(tmp_path / "xp.db"))
    assert history.database_path() == tmp_path / "history.db"
    assert not (tmp_path / "history.db").exists()  # readers must not create it
