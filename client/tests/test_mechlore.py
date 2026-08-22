"""How ;mechlore trains — these tests are the manual.

Forage grass, braid it to rope through the roundtimes, drop, repeat;
pause at mind-lock. The forage/braid wordings are keyword assumptions
until captures pin them (#71) — the classifier tests below say so.
"""

import importlib.util
import pathlib
from types import SimpleNamespace

REPO = pathlib.Path(__file__).parents[2]


def _mechlore():
    spec = importlib.util.spec_from_file_location(
        "mechlore_script", REPO / "scripts/mechlore.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mechlore = _mechlore()


class FakeHandle:
    """The script surface, with per-call canned answers per command."""

    def __init__(self, responses):
        self.responses = {c: list(seqs) for c, seqs in responses.items()}
        self.pending = []
        self.sent = []
        self.echoed = []
        self.state = SimpleNamespace(experience={})

    def put(self, command):
        self.sent.append(command)
        seqs = self.responses.get(command, [])
        self.pending = list(seqs.pop(0)) if seqs else []

    def get(self, timeout=None):
        return self.pending.pop(0) if self.pending else None

    def echo(self, text):
        self.echoed.append(text)

    def sleep(self, seconds):
        pass

    def waitrt(self):
        pass


def test_classify_forage_outcomes():
    # Synthetic wordings exercising the keyword rules (assumptions
    # until captured — #71).
    assert (
        mechlore.classify("You manage to find some grass!", mechlore.FORAGE_OUTCOMES)
        == "ok"
    )
    assert (
        mechlore.classify(
            "You forage around but find nothing.", mechlore.FORAGE_OUTCOMES
        )
        == "nothing_here"
    )
    assert (
        mechlore.classify("Your hands are full!", mechlore.FORAGE_OUTCOMES)
        == "hands_full"
    )
    assert (
        mechlore.classify("Something else entirely.", mechlore.FORAGE_OUTCOMES) is None
    )


def test_classify_braid_outcomes():
    assert (
        mechlore.classify(
            "You finish braiding, leaving a serviceable grass rope.",
            mechlore.BRAID_OUTCOMES,
        )
        == "done"
    )
    assert (
        mechlore.classify(
            "The grass is too damaged to braid further.", mechlore.BRAID_OUTCOMES
        )
        == "ruined"
    )
    assert (
        mechlore.classify("You braid the strands together.", mechlore.BRAID_OUTCOMES)
        == "progress"
    )


def test_braid_piece_braids_to_rope_and_drops_it(monkeypatch):
    monkeypatch.setattr(mechlore, "COLLECT_SECONDS", 0.02)
    monkeypatch.setattr(mechlore, "RESULT_SECONDS", 0.02)
    handle = FakeHandle(
        {
            "braid my grass": [
                ["You braid the strands together."],
                ["You finish braiding, leaving a grass rope."],
            ],
        }
    )
    braids = mechlore.braid_piece(handle)
    assert braids == 2
    assert handle.sent == ["braid my grass", "braid my grass", "drop my rope"]


def test_main_gives_up_somewhere_grassless(monkeypatch):
    monkeypatch.setattr(mechlore, "COLLECT_SECONDS", 0.02)
    monkeypatch.setattr(mechlore, "RESULT_SECONDS", 0.02)
    handle = FakeHandle(
        {
            "forage grass": [["You forage around but find nothing."]]
            * mechlore.FORAGE_FAILURES_BEFORE_GIVING_UP,
        }
    )
    mechlore.main(handle)
    assert any("move somewhere" in echo for echo in handle.echoed)


def test_unrecognized_answers_are_echoed_for_capture(monkeypatch):
    monkeypatch.setattr(mechlore, "COLLECT_SECONDS", 0.02)
    monkeypatch.setattr(mechlore, "RESULT_SECONDS", 0.02)
    monkeypatch.setattr(mechlore, "FORAGE_FAILURES_BEFORE_GIVING_UP", 1)
    handle = FakeHandle({"forage grass": [["Wholly novel game wording."]]})
    mechlore.main(handle)
    assert any(
        "unrecognized (forage): Wholly novel game wording." in echo
        for echo in handle.echoed
    )


def test_classify_blind_forage_as_nothing_here():
    # Captured live 2026-08-22: foraging an item the room can't supply
    # turns into a blind forage ("...can't quite seem to remember what
    # it was you were looking for").
    assert (
        mechlore.classify(
            "You begin to forage around, but can't quite seem to remember "
            "what it was you were looking for.",
            mechlore.FORAGE_OUTCOMES,
        )
        == "nothing_here"
    )


def test_find_nothing_is_not_a_find():
    # Failure needles are checked before "ok", so "You find nothing"
    # never hits the "you find" success needle.
    assert (
        mechlore.classify("You find nothing of interest.", mechlore.FORAGE_OUTCOMES)
        == "nothing_here"
    )


def test_ask_collects_the_result_that_lands_after_the_roundtime(monkeypatch):
    # Captured 2026-08-22: a 6s blind forage delivered its result only
    # when the roundtime expired, after the old collect window closed.
    monkeypatch.setattr(mechlore, "COLLECT_SECONDS", 0.02)
    monkeypatch.setattr(mechlore, "RESULT_SECONDS", 0.02)

    class RoundtimeHandle(FakeHandle):
        after_rt = []

        def waitrt(self):
            self.pending.extend(self.after_rt)
            self.after_rt = []

    handle = RoundtimeHandle(
        {
            "forage grass": [
                ["You wander around and poke your fingers into a few places."]
            ]
        }
    )
    handle.after_rt = ["You forage around but find nothing."]
    answer = mechlore.ask(handle, "forage grass")
    assert "find nothing" in answer
    assert mechlore.classify(answer, mechlore.FORAGE_OUTCOMES) == "nothing_here"
