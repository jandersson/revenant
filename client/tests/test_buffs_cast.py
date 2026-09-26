"""A CAST whose answer window closed on a bystander's line reads on
into a second window before it is called unrecognized (#294)."""

from types import SimpleNamespace

from client.game import buffs

READY = "You feel fully prepared to cast your spell.\n"
PREPARED = "You begin chanting a prayer to invoke the Footman's Strike spell.\n"
# Captured 2026-09-23 at 01:13 at the vineyard: a second cougar's
# approach came with its own prompt right after the CAST went out, the
# stream went quiet, and the spell's own line landed after the window.
APPROACH = "The cougar closes to melee range on you!\n"
STRUCK = "Your spell slams into the cougar!\n"


class Handle:
    def __init__(self, pending):
        self.pending = list(pending)
        self.sent = []
        self.state = SimpleNamespace(server_time=None)

    def put(self, command):
        self.sent.append(command)

    def get(self, timeout=None, streams=("",)):
        return self.pending.pop(0) if self.pending else None

    def sleep(self, seconds):
        pass

    def waitrt(self):
        pass


def _cast(handle, cast_answer):
    answers = {"prepare footman's strike 5": PREPARED, "cast": cast_answer}
    reported = []

    def ask(s, command):
        s.sent.append(command)
        return answers.get(command, "")

    state = SimpleNamespace(cast_at={})
    outcome = buffs.cast_once(
        handle,
        "footman's strike",
        5,
        state,
        ask,
        lambda kind, answer: reported.append((kind, answer)),
    )
    return outcome, reported


def test_a_bystanders_line_as_the_answer_is_read_past_into_the_spells_own(monkeypatch):
    monkeypatch.setattr(buffs, "CAST_TAIL_SECONDS", 0.6)
    # The ready line ends the prepare wait; the spell's line waits in the
    # stream for the second window.
    handle = Handle([READY, STRUCK])
    outcome, reported = _cast(handle, APPROACH)
    assert outcome == "ok"
    assert reported == []
    assert handle.pending == []  # the second window took the line


def test_a_second_window_with_nothing_in_it_still_reports_the_answer(monkeypatch):
    monkeypatch.setattr(buffs, "CAST_TAIL_SECONDS", 0.6)
    handle = Handle([READY])
    outcome, reported = _cast(handle, APPROACH)
    assert outcome == "ok"  # as before: an unread answer is not a failure
    assert reported == [("cast", APPROACH)]


def test_a_recognized_answer_opens_no_second_window(monkeypatch):
    monkeypatch.setattr(buffs, "CAST_TAIL_SECONDS", 0.6)
    handle = Handle([READY, APPROACH])
    outcome, reported = _cast(handle, STRUCK)
    assert outcome == "ok" and reported == []
    assert handle.pending == [APPROACH]  # left in the stream, unread


# Captured 2026-09-23 at 16:00: nothing was held when the CAST went out.
NOT_PREPARED = "You don't have a spell prepared!\n"


def test_a_cast_with_nothing_prepared_is_a_failed_cast_not_a_mystery(monkeypatch):
    monkeypatch.setattr(buffs, "CAST_TAIL_SECONDS", 0.6)
    handle = Handle([READY])
    outcome, reported = _cast(handle, NOT_PREPARED)
    assert outcome == "collapsed"
    assert reported == []
    assert "release" not in handle.sent


def test_a_name_the_game_does_not_parse_is_prepared_by_its_abbreviation(
    tmp_path, monkeypatch
):
    # 2026-09-26 (#320): "prepare hands of justice" answered "You have no
    # idea how to cast that spell." every hunt while "prepare hoj" is the
    # spell; ;sheet records the abbreviation off SPELLS in history.db.
    import sqlite3

    db = tmp_path / "history.db"
    with sqlite3.connect(str(db)) as connection:
        connection.execute(
            "CREATE TABLE spells (seq INTEGER PRIMARY KEY, logged_at TEXT,"
            " character_name TEXT, name TEXT, abbrev TEXT, kind TEXT, chapter TEXT)"
        )
        connection.execute(
            "INSERT INTO spells (logged_at, character_name, name, abbrev, kind,"
            " chapter) VALUES ('t', 'Lanival', 'Hands of Justice', 'hoj',"
            " 'learned', 'Justice')"
        )
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(db))
    handle = Handle([])
    handle.state.name = "Lanival"
    answers = {
        "prepare hands of justice": "You have no idea how to cast that spell.\n",
        "prepare hoj": "You clasp your hands together and chant a brief prayer.\n",
    }

    def ask(s, command):
        s.sent.append(command)
        return answers.get(command, "")

    buffs.cast_once(
        handle,
        "hands of justice",
        0,
        SimpleNamespace(cast_at={}),
        ask,
        lambda kind, answer: None,
    )
    assert handle.sent[:2] == ["prepare hands of justice", "prepare hoj"]


def test_a_room_that_blocks_magic_is_a_failed_prepare():
    # Captured 2026-09-26 in the Paladins' guild library.
    from client.game.probe import classify

    blocked = "Something in the area interferes with your spell preparations.\n"
    assert classify(blocked, buffs.PREPARE_OUTCOMES) == "failed"
    unknown = "You have no idea how to cast that spell.\n"
    assert classify(unknown, buffs.PREPARE_OUTCOMES) == "failed"


def test_the_hands_of_justice_cast_is_a_cast():
    # Captured 2026-09-26, the first live cast (#320).
    from client.game.probe import classify

    cast = (
        "You clasp your hands together and chant a brief prayer for Chadatru's "
        "divine guidance.\nYour hands glow briefly with a pristine white light as "
        "you feel your dedication to the pursuit of justice strengthened!\n"
    )
    assert classify(cast, buffs.CAST_OUTCOMES) == "ok"
