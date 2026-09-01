"""client.probe: ask the game a question, classify the answer by keyword.

Shared by ;mechlore and ;favors — each script's own tests cover its
outcome tables; these pin the mechanics they both lean on."""

from client import probe

OUTCOMES = (
    ("nothing_here", ("find nothing", "nothing like that")),
    ("ok", ("you find",)),
)


class FakeHandle:
    """A script handle whose put() queues canned lines for get(), and
    whose waitrt() releases the lines the game held until the roundtime
    ended."""

    def __init__(self, answers, after_roundtime=()):
        self.answers = list(answers)
        self.after_roundtime = list(after_roundtime)
        self.pending = []
        self.sent = []

    def put(self, command):
        self.sent.append(command)
        self.pending = list(self.answers)

    def get(self, timeout=None, streams=("",)):
        return self.pending.pop(0) if self.pending else None

    def waitrt(self):
        self.pending.extend(self.after_roundtime)


def test_classify_returns_the_first_matching_outcome_in_table_order():
    # Failure needles ahead of success ones: "you find nothing" also
    # contains "you find", and the table order decides which wins.
    assert probe.classify("You find nothing of interest.", OUTCOMES) == "nothing_here"
    assert probe.classify("You find some grass!", OUTCOMES) == "ok"


def test_classify_is_case_insensitive_and_none_when_nothing_matches():
    assert probe.classify("NOTHING LIKE THAT here.", OUTCOMES) == "nothing_here"
    assert probe.classify("Something else entirely.", OUTCOMES) is None


def test_collect_joins_the_lines_within_the_window():
    handle = FakeHandle(["one", "two"])
    handle.put("look")
    assert probe.collect(handle, 0.02) == "one\ntwo"


def test_collect_is_empty_when_nothing_arrives():
    assert probe.collect(FakeHandle([]), 0.02) == ""


def test_ask_sends_the_command_and_returns_the_opening_lines():
    handle = FakeHandle(["You wander around and poke your fingers about."])
    answer = probe.ask(handle, "forage grass", 0.02, 0.02)
    assert handle.sent == ["forage grass"]
    assert answer == "You wander around and poke your fingers about."


def test_ask_includes_the_result_that_lands_after_the_roundtime():
    # Captured 2026-08-22: a 6s blind forage answered only when the
    # roundtime expired — a single collect window before waitrt missed it.
    handle = FakeHandle(
        ["You wander around and poke your fingers about."],
        after_roundtime=["You forage around but find nothing."],
    )
    answer = probe.ask(handle, "forage grass", 0.02, 0.02)
    assert "find nothing" in answer
    assert probe.classify(answer, OUTCOMES) == "nothing_here"
