"""How ;circle answers — the manual.

The script computes the guildleader's advice from INFO's circle and
guild now over the latest ;sheet snapshot's ranks in xp.db; INFO is
the one command sent. The model itself is pinned in test_circles; here
we cover the script's reading and report.
"""

import importlib.util
import pathlib
import sqlite3

from test_circles import ROSTER
from test_sheet import sheet

REPO = pathlib.Path(__file__).parents[2]


def _circle():
    spec = importlib.util.spec_from_file_location(
        "circle_script", REPO / "scripts/circle.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


circle = _circle()


class FakeHandle:
    """INFO answers `info` (nothing by default: the snapshot's circle
    stands in); every other command answers silence."""

    state = None

    def __init__(self, info=""):
        self.echoed = []
        self.sent = []
        self.pending = []
        self.info = info

    def echo(self, text):
        self.echoed.append(text)

    def put(self, command):
        self.sent.append(command)
        self.pending = (
            [line + "\n" for line in self.info.splitlines()]
            if command == "info"
            else []
        )

    def get(self, timeout=None, streams=("",)):
        return self.pending.pop(0) if self.pending else None

    def sleep(self, seconds):
        pass

    def waitrt(self):
        pass


def seed_snapshot(path, character="Lanival", logged_at="2026-08-22T12:00:00+00:00"):
    connection = sqlite3.connect(path)
    sheet.ensure_schema(connection)
    connection.executemany(
        "INSERT INTO sheet_skills"
        " (logged_at, character_name, skill_name, rank, percent)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (logged_at, character, skill, rank, percent)
            for skill, (rank, percent) in ROSTER.items()
        ],
    )
    connection.execute(
        "INSERT INTO character"
        " (logged_at, character_name, circle, tdps, favors, guild)"
        " VALUES (?, ?, 1, 356, 0, 'Thief')",
        (logged_at, character),
    )
    connection.commit()
    connection.close()


def test_circle_reports_gates_from_the_latest_snapshot(monkeypatch, tmp_path):
    database = tmp_path / "xp.db"
    seed_snapshot(database)
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(database))
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")
    handle = FakeHandle()
    circle.main(handle)
    text = "\n".join(handle.echoed)
    assert "gates to circle 2:" in text
    assert "armor: 1st Armor (Light Armor) 3/4" in text
    assert "weapon: 1st Weapon (Small Edged) 3/6, Parry Ability 1/2" in text
    assert "1st Supernatural (Augmentation) 1/2" in text
    assert "8th Survival (First Aid) 1/2" in text
    assert "circle 1 Thief from the sheet" in text
    assert "from Lanival's sheet snapshot" in text
    assert handle.sent == ["info"]


def test_infos_circle_and_guild_now_beat_the_snapshots(monkeypatch, tmp_path):
    # The snapshot says circle 1; INFO says the character is circle 2 now
    # (a sheet several circles old gated a circle already passed, the
    # operator 2026-09-20). INFO is read-only, no roundtime.
    database = tmp_path / "xp.db"
    seed_snapshot(database)
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(database))
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")
    handle = FakeHandle(
        info="Name: Lanival  Guild: Thief  Race: Human\nGender: Male   Age: 20   Circle: 2\n"
    )
    circle.main(handle)
    text = "\n".join(handle.echoed)
    assert "gates to circle 3:" in text
    assert "circle 2 Thief from INFO now" in text


def test_circle_without_a_snapshot_points_at_sheet(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "xp.db"))
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")
    handle = FakeHandle()
    circle.main(handle)
    assert any("run ;sheet once first" in line for line in handle.echoed)


def test_circle_for_a_guild_without_circles(monkeypatch, tmp_path):
    database = tmp_path / "xp.db"
    seed_snapshot(database)
    connection = sqlite3.connect(database)
    connection.execute("UPDATE character SET guild = 'Commoner'")
    connection.commit()
    connection.close()
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(database))
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")
    handle = FakeHandle()
    circle.main(handle)
    assert any(
        "don't circle" in line for line in handle.echoed
    )  # not "unknown guild" (#133)


def test_a_commoner_is_told_commoners_do_not_circle():
    from client.game import circles

    assert circles.gates({}, 0, "Commoner") is None
    assert circles.explain_no_gates("Commoner") == (
        "Commoners don't circle — join a guild, and ;circle will report "
        "what gates the next one"
    )
    assert circles.explain_no_gates("Muppet") == (
        "no circle requirements known for guild 'Muppet'"
    )


def test_the_exp_windows_ranks_lie_over_the_snapshot(monkeypatch, tmp_path):
    # Parry Ability is 1/2 in the snapshot; the window says rank 2 now.
    database = tmp_path / "xp.db"
    seed_snapshot(database)
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(database))
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")
    handle = FakeHandle()
    from types import SimpleNamespace

    handle.state = SimpleNamespace(
        name="Lanival",
        experience={"Parry Ability": {"rank": 2, "percent": 10, "mindstate": 5}},
    )
    circle.main(handle)
    text = "\n".join(handle.echoed)
    assert "Parry Ability 1/2" not in text
    assert "1st Weapon (Small Edged) 3/6" in text
    assert "the exp window's ranks over it" in text


def test_overlay_never_lowers_a_snapshot_rank():
    from client.game import circles

    merged = circles.overlay_live(
        {"Evasion": (10, 50), "Tactics": (3, 0)},
        {"Evasion": (9, 0), "Tactics": {"rank": 4, "percent": 1}, "New": {"rank": 1}},
    )
    assert merged == {"Evasion": (10, 50), "Tactics": (4, 1), "New": (1, 0)}


def test_fresh_asks_the_running_sheet_for_a_snapshot_and_waits_for_it(
    monkeypatch, tmp_path
):
    database = tmp_path / "xp.db"
    seed_snapshot(database)
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(database))
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")

    class Runner(FakeHandle):
        args = ["fresh"]
        told, started, slept = [], [], 0

        def is_running(self, name):
            return name == "sheet"  # the autostart is up, as always

        def tell(self, name, line):
            self.told.append((name, line))
            return True

        def run(self, name, args=()):
            self.started.append(name)
            return True

        def sleep(self, seconds):
            self.slept += 1
            if self.slept == 2:  # the snapshot lands on the second look
                seed_snapshot(database, logged_at="2026-08-22T13:00:00+00:00")

    handle = Runner()
    circle.main(handle)
    assert handle.told == [("sheet", "once")]
    assert handle.started == []
    assert handle.slept == 2
    assert any("gates to circle 2:" in line for line in handle.echoed)


def test_fresh_from_cold_starts_sheet_once(monkeypatch, tmp_path):
    database = tmp_path / "xp.db"
    seed_snapshot(database)
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(database))
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")
    circle.SHEET_WAIT = 2

    class Runner(FakeHandle):
        args = ["fresh"]
        started = []

        def is_running(self, name):
            return False

        def run(self, name, args=()):
            self.started.append((name, list(args)))
            return True

        def sleep(self, seconds):
            pass

    handle = Runner()
    circle.main(handle)
    assert handle.started == [("sheet", ["once"])]
    assert any("no fresh sheet in 2s" in line for line in handle.echoed)
    assert any("gates to circle 2:" in line for line in handle.echoed)
