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
