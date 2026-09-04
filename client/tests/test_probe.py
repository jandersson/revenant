"""client.probe: ask the game a question, classify the answer by keyword.

Shared by ;mechlore and ;favors — each script's own tests cover its
outcome tables; these pin the mechanics they both lean on."""

from client import probe

OUTCOMES = (
    ("nothing_here", ("find nothing", "nothing like that")),
    ("ok", ("you find",)),
)


class FakeHandle:
    """A script handle whose put() queues canned pieces for get(), and
    whose waitrt() releases the lines the game held until the roundtime
    ended. Pieces are what the engine delivers: the last piece of every
    game line ends in a newline (core.Engine.read)."""

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
    handle = FakeHandle(["one\n", "two\n"])
    handle.put("look")
    assert probe.collect(handle, 0.02) == "one\ntwo"


def test_collect_glues_a_line_delivered_in_pieces():
    # A styled or linked line reaches a script as several pieces, only
    # the last carrying the newline. INV LIST's nested items are
    # "     -" plus a <d>-linked name: torn apart, the parser lost the
    # nesting (#123).
    handle = FakeHandle(["  ", "an ornate scabbard\n", "     -", "a short sword\n"])
    handle.put("inv list")
    assert probe.collect(handle, 0.02) == "  an ornate scabbard\n     -a short sword"


def test_collect_stops_at_the_answers_last_line():
    handle = FakeHandle(["Circle: 1\n", "Time Development Points: 356\n", "later\n"])
    handle.put("exp all")
    assert probe.collect(handle, 0.02, until="Development Points") == (
        "Circle: 1\nTime Development Points: 356"
    )
    assert handle.pending == ["later\n"]  # left for whoever reads next


def test_collect_keeps_a_piece_the_window_cut_off():
    handle = FakeHandle(["half a line"])
    handle.put("look")
    assert probe.collect(handle, 0.02) == "half a line"


def test_collect_is_empty_when_nothing_arrives():
    assert probe.collect(FakeHandle([]), 0.02) == ""


def test_ask_sends_the_command_and_returns_the_opening_lines():
    handle = FakeHandle(["You wander around and poke your fingers about.\n"])
    answer = probe.ask(handle, "forage grass", 0.02, 0.02)
    assert handle.sent == ["forage grass"]
    assert answer == "You wander around and poke your fingers about."


def test_ask_includes_the_result_that_lands_after_the_roundtime():
    # Captured 2026-08-22: a 6s blind forage answered only when the
    # roundtime expired — a single collect window before waitrt missed it.
    handle = FakeHandle(
        ["You wander around and poke your fingers about.\n"],
        after_roundtime=["You forage around but find nothing.\n"],
    )
    answer = probe.ask(handle, "forage grass", 0.02, 0.02)
    assert "find nothing" in answer
    assert probe.classify(answer, OUTCOMES) == "nothing_here"
