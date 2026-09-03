"""How ;sheet parses and stores the character sheet — the manual.

Fixtures mirror captured INFO / EXP ALL output (2026-08-22), scrubbed
to synthetic identity per the no-PII rule; the numeric layout is real.
"""

import importlib.util
import pathlib
import sqlite3

REPO = pathlib.Path(__file__).parents[2]


def _sheet():
    spec = importlib.util.spec_from_file_location(
        "sheet_script", REPO / "scripts/sheet.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sheet = _sheet()

INFO_TEXT = """Name: Testchar Example   Race: Human   Guild: Commoner
Gender: Male   Age: 20   Circle: 1
     Strength :  10              Reflex :  14
      Agility :   9            Charisma :  10
   Discipline :   5              Wisdom :   6
 Intelligence :   8             Stamina :   8
Concentration : 317    Max : 317
       Favors : 0
         TDPs : 356
  Encumbrance : None
"""

EXP_ALL_TEXT = """Circle: 1
Showing all skills that you have skill in.
          SKILL: Rank/Percent towards next rank/Amount learning/Mindstate Fraction
     Light Armor:      3 10% clear          (0/34)       Defending:      2 36% clear          (0/34)
         Evasion:      3 34% clear          (0/34)       Athletics:     22 17% clear          (0/34)
 Mechanical Lore:      3 00% clear          (0/34)         Tactics:      1 28% clear          (0/34)
Total Ranks Displayed: 66
Time Development Points: 356  Favors: 0  Deaths: 0  Departs: 0
"""


def test_parse_info_reads_stats_circle_tdps_favors():
    info = sheet.parse_info(INFO_TEXT)
    assert info["stats"] == {
        "Strength": 10,
        "Reflex": 14,
        "Agility": 9,
        "Charisma": 10,
        "Discipline": 5,
        "Wisdom": 6,
        "Intelligence": 8,
        "Stamina": 8,
    }
    assert info["circle"] == 1
    assert info["tdps"] == 356
    assert info["favors"] == 0
    assert info["guild"] == "Commoner"


def test_parse_exp_all_reads_both_columns():
    skills = sheet.parse_exp_all(EXP_ALL_TEXT)
    assert skills["Athletics"] == (22, 17)
    assert skills["Light Armor"] == (3, 10)
    assert skills["Mechanical Lore"] == (3, 0)
    assert len(skills) == 6
    assert "SKILL" not in skills  # the header row never parses as a skill


class FakeHandle:
    """The script-engine surface ;sheet uses, with per-attempt canned
    answers: responses[command] is a list of answers, consumed one per
    put()."""

    def __init__(self, responses):
        self.responses = {c: list(seqs) for c, seqs in responses.items()}
        self.pending = []
        self.echoed = []
        self.slept = 0
        self.state = None
        self.dead = False

    def put(self, command):
        seqs = self.responses.get(command, [])
        self.pending = list(seqs.pop(0)) if seqs else []

    def get(self, timeout=None):
        return self.pending.pop(0) if self.pending else None

    def echo(self, text):
        self.echoed.append(text)

    def sleep(self, seconds):
        self.slept += seconds


def snapshot_into(monkeypatch, tmp_path, responses):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "xp.db"))
    monkeypatch.setenv("REVENANT_CHARACTER", "Testchar")
    monkeypatch.setattr(sheet, "COLLECT_SECONDS", 0.05)
    handle = FakeHandle(responses)
    sheet.snapshot(handle)
    connection = sqlite3.connect(tmp_path / "xp.db")
    return handle, connection


def test_snapshot_reasks_a_command_the_game_ate(monkeypatch, tmp_path):
    # Captured 2026-08-22 (#65): the session-start INFO went
    # unanswered while EXP ALL answered fine. The re-ask recovers it.
    handle, connection = snapshot_into(
        monkeypatch,
        tmp_path,
        {
            "info": [[], INFO_TEXT.splitlines()],
            "exp all": [EXP_ALL_TEXT.splitlines()],
        },
    )
    assert handle.slept > 0  # a retry pause happened
    circle, tdps = connection.execute("SELECT circle, tdps FROM character").fetchone()
    assert (circle, tdps) == (1, 356)
    assert any("circle 1" in line for line in handle.echoed)


def test_snapshot_never_stores_an_all_none_character_row(monkeypatch, tmp_path):
    handle, connection = snapshot_into(
        monkeypatch,
        tmp_path,
        {
            "info": [[], [], []],  # every ask goes unanswered
            "exp all": [EXP_ALL_TEXT.splitlines()],
        },
    )
    assert connection.execute("SELECT count(*) FROM character").fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM stats").fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM sheet_skills").fetchone()[0] == 6
    assert any("INFO went unanswered" in line for line in handle.echoed)


def test_ensure_schema_adds_guild_to_a_pre_tracking_database():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE character (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " logged_at TEXT NOT NULL, character_name TEXT NOT NULL,"
        " circle INTEGER, tdps INTEGER, favors INTEGER)"
    )
    sheet.ensure_schema(connection)
    sheet.ensure_schema(connection)  # idempotent on migrated databases
    columns = [row[1] for row in connection.execute("PRAGMA table_info(character)")]
    assert "guild" in columns


def test_collect_stops_at_an_explicit_final_line():
    handle = FakeHandle({})
    handle.pending = INFO_TEXT.splitlines() + ["later, unrelated text"]
    text = sheet.collect(handle, seconds=5, until="Encumbrance")
    assert "Encumbrance" in text
    # The final line ended the wait: what followed was never consumed.
    assert handle.pending == ["later, unrelated text"]


def test_info_runs_its_whole_window():
    # INFO has no reliable final line — Wealth and Debt trail
    # Encumbrance, and the Debt block only exists for debtors. An
    # "Encumbrance" early-exit silently cut the wealth capture off
    # (captured live: a snapshot stored no wealth rows).
    assert sheet.INFO_END is None


def test_snapshot_rows_roundtrip_through_the_database():
    connection = sqlite3.connect(":memory:")
    sheet.ensure_schema(connection)
    sheet.ensure_schema(connection)  # idempotent
    sheet.insert_snapshot(
        connection,
        "Testchar",
        "2026-08-22T12:00:00+00:00",
        sheet.parse_info(INFO_TEXT),
        sheet.parse_exp_all(EXP_ALL_TEXT),
    )
    assert connection.execute("SELECT count(*) FROM stats").fetchone()[0] == 8
    assert connection.execute("SELECT count(*) FROM sheet_skills").fetchone()[0] == 6
    circle, tdps, favors, guild = connection.execute(
        "SELECT circle, tdps, favors, guild FROM character"
    ).fetchone()
    assert (circle, tdps, favors, guild) == (1, 356, 0, "Commoner")
    top = connection.execute(
        "SELECT skill_name, rank FROM sheet_skills ORDER BY rank DESC LIMIT 1"
    ).fetchone()
    assert tuple(top) == ("Athletics", 22)


def test_a_ghost_is_not_interrogated(monkeypatch):
    # Captured live (#93): a dead character was asked INFO three times
    # and EXP ALL three times, answered only by the ghost warning.
    # Dead now means defer — snapshot never runs on a corpse.
    handle = FakeHandle({})
    handle.dead = True
    handle.args = ["once"]

    def boom(s):
        raise AssertionError("snapshot ran on a corpse")

    monkeypatch.setattr(sheet, "snapshot", boom)
    sheet.main(handle)
    assert any("ghost" in echo for echo in handle.echoed)


def test_parse_wealth_reads_the_copper_parentheticals():
    # Captured live from INFO (an Empath with modest means and a debt):
    text = (
        "Wealth:\n"
        "  No Kronars.\n"
        "  11 copper Lirums (11 copper Lirums).\n"
        "  6 copper Dokoras (6 copper Dokoras).\n"
        "Debt:\n"
        "  You owe 9 bronze Kronars to the Principality of Zoluren."
        " (90 copper Kronars)\n"
    )
    assert sheet.parse_wealth(text) == {
        "carried": {"Lirums": 11, "Dokoras": 6},
        "debt": {"Kronars": 90},
    }


# Captured 2026-09-03 (#112) — the renaming room's answer to EXP ALL. A
# character sent there for a name that does not fit the setting gets
# this reminder in place of every command's own output.
RENAMING_TEXT = """Testchar, this is a reminder that you have been sent to this room \
so you may change your name to something which fits the medieval fantasy \
environment of DragonRealms.  If you are not sure why you have been sent here, \
type ADVICE.  Otherwise, type LOOK and follow the directions you see.  Any \
inventory you have will be saved and returned to you automatically once you \
enter the live game world as long as you reroll within two hours after you type \
CHECK IN.  Thank you.
Your name: Testchar Distresseater.  For help, type ADVICE."""


def test_blocked_by_renaming_recognizes_the_rooms_reminder():
    assert sheet.blocked_by_renaming(RENAMING_TEXT) is True


def test_an_ordinary_answer_is_not_a_renaming_refusal():
    assert sheet.blocked_by_renaming(EXP_ALL_TEXT) is False
    assert sheet.blocked_by_renaming("") is False


def test_the_renaming_room_stops_the_retries(monkeypatch, tmp_path):
    # The regression: three EXP ALL attempts against a room that answers
    # everything the same way, costing ATTEMPTS * RETRY_SLEEP seconds for
    # nothing. One ask is enough to know.
    handle, connection = snapshot_into(
        monkeypatch,
        tmp_path,
        {
            "info": [INFO_TEXT.splitlines()],
            "exp all": [
                RENAMING_TEXT.splitlines(),
                RENAMING_TEXT.splitlines(),
                RENAMING_TEXT.splitlines(),
            ],
        },
    )
    # Only the first "exp all" was consumed; the other two are untouched.
    assert len(handle.responses["exp all"]) == 2
    assert handle.slept == 0
    assert any("renaming room" in line for line in handle.echoed)


def test_the_stats_still_land_when_only_exp_all_is_refused(monkeypatch, tmp_path):
    # INFO answers in the renaming room even though EXP ALL does not, so
    # the snapshot keeps what it could read rather than storing nothing.
    handle, connection = snapshot_into(
        monkeypatch,
        tmp_path,
        {
            "info": [INFO_TEXT.splitlines()],
            "exp all": [RENAMING_TEXT.splitlines()],
        },
    )
    stats = connection.execute("select count(*) from stats").fetchone()[0]
    skills = connection.execute("select count(*) from sheet_skills").fetchone()[0]
    assert stats > 0
    assert skills == 0


# Captured 2026-09-03 (#113) — Viterbi, a circle-0 Commoner: EXP ALL
# answers completely and says there is nothing to show. The answer
# carries EXP_ALL_END, so it is an answer, not silence.
EMPTY_EXP_ALL_TEXT = """Showing all skills that you have skill in.
          SKILL: Rank/Percent towards next rank/Amount learning/Mindstate Fraction
        No skills have field experience or none meet your criteria!
Total Ranks Displayed: 0
Time Development Points: 600  Favors: 0  Deaths: 0  Departs: 0"""


def test_an_untrained_characters_empty_exp_all_is_asked_once(monkeypatch, tmp_path):
    # The regression: bool({}) is False, so an empty-but-complete answer
    # looked unanswered and was re-asked ATTEMPTS times for nothing.
    handle, connection = snapshot_into(
        monkeypatch,
        tmp_path,
        {
            "info": [INFO_TEXT.splitlines()],
            "exp all": [
                EMPTY_EXP_ALL_TEXT.splitlines(),
                EMPTY_EXP_ALL_TEXT.splitlines(),
                EMPTY_EXP_ALL_TEXT.splitlines(),
            ],
        },
    )
    assert len(handle.responses["exp all"]) == 2  # only the first was used
    assert handle.slept == 0  # no RETRY_SLEEP burned


def test_an_empty_exp_all_stores_the_stats_and_no_skills(monkeypatch, tmp_path):
    handle, connection = snapshot_into(
        monkeypatch,
        tmp_path,
        {
            "info": [INFO_TEXT.splitlines()],
            "exp all": [EMPTY_EXP_ALL_TEXT.splitlines()],
        },
    )
    assert connection.execute("select count(*) from stats").fetchone()[0] > 0
    assert connection.execute("select count(*) from sheet_skills").fetchone()[0] == 0


def test_a_genuinely_silent_exp_all_is_still_reasked(monkeypatch, tmp_path):
    # The #65 behaviour must survive: no answer at all still retries,
    # and the retry's real answer is what gets stored.
    handle, connection = snapshot_into(
        monkeypatch,
        tmp_path,
        {
            "info": [INFO_TEXT.splitlines()],
            "exp all": [[], EXP_ALL_TEXT.splitlines()],
        },
    )
    assert handle.slept > 0  # it waited and asked again
    assert connection.execute("select count(*) from sheet_skills").fetchone()[0] > 0


# --- the identity trio: race, gender, birth date (#115) ---

# Captured 2026-09-03 — INFO carries a birth line the snapshot used to
# discard, so a character's age lived only in the raw game logs.
INFO_WITH_BIRTH = (
    INFO_TEXT
    + """You were born on the 29th day of the 4th month of Shorka the Cobra in the \
year of the Golden Panther, 338 years after the victory of Lanival the Redeemer.
"""
)

# Doc, an unset birth date: day 1, month 1, year 0 — the calendar epoch,
# reported by characters that never finished creation. Year 0 is a real
# answer and must survive as 0, not be coerced to NULL.
INFO_EPOCH_BIRTH = """Name: Testchar Holiday   Race: Human   Guild: Commoner
Gender: Male   Age: 457   Circle: 0
     Strength :   6              Reflex :  10
       Favors : 0
         TDPs : 304
You were born on the 1st day of the 1st month of Akroeg the Ram in the year of \
the Silver Unicorn, 0 years after the victory of Lanival the Redeemer.
"""


def test_parse_info_reads_race_and_gender():
    parsed = sheet.parse_info(INFO_TEXT)
    assert parsed["race"] == "Human"
    assert parsed["gender"] == "Male"


def test_parse_info_reads_the_birth_date():
    parsed = sheet.parse_info(INFO_WITH_BIRTH)
    assert (parsed["birth_day"], parsed["birth_month"], parsed["birth_year"]) == (
        29,
        4,
        338,
    )


def test_an_unset_birth_date_survives_as_year_zero():
    # Not a missing value: 457 - 0 is exactly the age the game reports.
    parsed = sheet.parse_info(INFO_EPOCH_BIRTH)
    assert parsed["birth_year"] == 0
    assert parsed["birth_day"] == 1
    assert parsed["birth_month"] == 1


def test_info_without_a_birth_line_leaves_the_date_empty():
    parsed = sheet.parse_info(INFO_TEXT)
    assert parsed["birth_year"] is None
    assert parsed["birth_day"] is None


def test_parse_info_does_not_store_age():
    # Age is current year minus birth_year; eltime knows the year, and a
    # stored age would go stale in the table.
    assert "age" not in sheet.parse_info(INFO_WITH_BIRTH)


def test_the_identity_columns_land_in_the_snapshot(monkeypatch, tmp_path):
    handle, connection = snapshot_into(
        monkeypatch,
        tmp_path,
        {
            "info": [INFO_WITH_BIRTH.splitlines()],
            "exp all": [EXP_ALL_TEXT.splitlines()],
        },
    )
    row = connection.execute(
        "SELECT race, gender, birth_year, birth_day, birth_month FROM character"
    ).fetchone()
    assert row == ("Human", "Male", 338, 29, 4)


def test_ensure_schema_adds_the_columns_to_an_older_database(tmp_path):
    # A database written before these columns existed: CREATE IF NOT
    # EXISTS won't touch it, so the additive migration has to.
    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE character (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " logged_at TEXT NOT NULL, character_name TEXT NOT NULL,"
        " circle INTEGER, tdps INTEGER, favors INTEGER);"
    )
    connection.execute(
        "INSERT INTO character (logged_at, character_name, circle)"
        " VALUES ('2026-01-01', 'Testchar', 5)"
    )
    connection.commit()
    sheet.ensure_schema(connection)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(character)")}
    assert {
        "guild",
        "race",
        "gender",
        "birth_year",
        "birth_day",
        "birth_month",
    } <= columns
    # The existing row survives, with NULLs for what it never had.
    assert connection.execute(
        "SELECT circle, race FROM character WHERE character_name = 'Testchar'"
    ).fetchone() == (5, None)
