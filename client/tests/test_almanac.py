"""The almanac — these tests are the manual. One STUDY fills a random
skill's pool by half, then the book rests ten minutes; the game's own
countdown sets the next try, and the timer is shared by every script
(client/game/almanac.py). Captured 2026-09-28 on the diamond-hide
almanac."""

from types import SimpleNamespace

import pytest

from client.game import almanac

STUDIED = (
    "You set about studying your diamond-hide almanac intently.  You believe "
    "you've learned something significant about Bow!\nRoundtime: 10 seconds\n"
)
GLEANED = (
    "You've gleaned all the insight you can from the diamond-hide almanac, for "
    "now.\n[Please try again in 9 roisaen.]\n"
)
CLOSED = (
    "The text of the diamond-hide almanac initially appears like gibberish, but "
    "immediately resolves into legible words.\nYou believe you would learn "
    "something significant about a random skill if you were to OPEN the "
    "diamond-hide almanac and STUDY its contents.\n"
)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(almanac, "clock", lambda: now["t"])
    monkeypatch.setattr(almanac, "_NEXT", {})
    monkeypatch.setattr(almanac, "_OFF", set())
    monkeypatch.setattr(almanac, "STUDIED", [])
    return now


def handle(left=None, right=None):
    echoed = []
    return SimpleNamespace(
        state=SimpleNamespace(left_hand=left, right_hand=right),
        echo=echoed.append,
        echoed=echoed,
        waitrt=lambda: None,
        dead=False,
    )


def asker(answers):
    sent = []

    def ask(s, command):
        sent.append(command)
        for prefix, text in answers.items():
            if command.startswith(prefix):
                return text
        return ""

    return ask, sent


def test_the_answers_read_as_learned_waiting_or_closed():
    assert almanac.answer(STUDIED) == ("learned", "Bow", 600)
    assert almanac.answer(GLEANED) == ("waiting", None, 600)  # rounded up
    assert almanac.answer(CLOSED) == ("closed", None, 0)
    assert almanac.answer("Something odd.") == (None, None, 0)


def test_a_ready_almanac_is_got_studied_and_stowed(fresh):
    s = handle(right={"noun": "scimitar"})
    ask, sent = asker(
        {"get my almanac": "You get a diamond-hide almanac.", "study": STUDIED}
    )
    assert almanac.study(s, "almanac", ask, "hunt") == "Bow"
    assert sent == ["get my almanac", "study my almanac", "stow my almanac"]
    assert "hunt: almanac studied — Bow" in s.echoed
    assert almanac.STUDIED == ["Bow"]  # the session's record, for ;train's rest (#412)
    # The timer is shared: nothing is sent until it runs out.
    assert almanac.study(s, "almanac", ask, "train") is None and len(sent) == 3
    fresh["t"] += 621
    assert almanac.ready("almanac")


def test_the_countdown_sets_the_next_try_and_a_book_in_hand_stays_there(fresh):
    s = handle(left={"noun": "almanac"})
    ask, sent = asker({"study": GLEANED})
    almanac.study(s, "almanac", ask, "train")
    assert sent == ["study my almanac"]  # no GET, no STOW
    assert almanac._NEXT["almanac"] == 1000.0 + 600 + 20


def test_a_closed_almanac_is_opened_and_studied_again(fresh):
    # 2026-10-01: OPEN went out before every study and an open book
    # answered "But the diamond-hide almanac isn't closed!" each time.
    s = handle()
    said = iter([CLOSED, STUDIED])
    sent = []

    def ask(s, command):
        sent.append(command)
        return next(said) if command.startswith("study") else ""

    assert almanac.study(s, "almanac", ask, "train") == "Bow"
    assert sent == [
        "get my almanac",
        "study my almanac",
        "open my almanac",
        "study my almanac",
        "stow my almanac",
    ]


def test_no_almanac_on_you_is_off_and_full_hands_wait():
    ask, sent = asker({"get my almanac": "What were you referring to?"})
    s = handle()
    almanac.study(s, "almanac", ask, "train")
    assert sent == ["get my almanac"] and not almanac.ready("almanac")
    busy = handle(left={"noun": "mortar"}, right={"noun": "pestle"})
    ask, sent = asker({})
    almanac.study(busy, "book", ask, "train")
    assert sent == []
