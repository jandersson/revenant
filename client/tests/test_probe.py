"""client.game.probe: ask the game a question, classify the answer by keyword.

Shared by ;mechlore and ;favors — each script's own tests cover its
outcome tables; these pin the mechanics they both lean on."""

import time
from types import SimpleNamespace

from client.game import probe

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


class PromptedHandle(FakeHandle):
    """A handle with a parser state that counts prompts (#248): the
    answer's pieces arrive, then the prompt that closes them; lines the
    roundtime holds back come with a prompt of their own after waitrt.
    `intruder` is an unrelated line and its prompt landing right after
    the send, before the answer."""

    def __init__(self, answers, after_roundtime=(), roundtime=0, intruder=None):
        super().__init__(answers, after_roundtime)
        self.state = SimpleNamespace(
            prompt_count=10, server_time=100, roundtime=0, casttime=0
        )
        self.roundtime = roundtime
        self.intruder = intruder
        self.waited = False
        self.due_at = None

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        if self.intruder:
            self.pending = [self.intruder]
            self.due_at = time.monotonic() + 0.1  # the answer, a beat later
        else:
            self.pending = list(self.answers)

    def get(self, timeout=None, streams=("",)):
        if self.due_at is not None and time.monotonic() >= self.due_at:
            self.pending.extend(self.answers)
            self.due_at = None
        if self.pending:
            piece = self.pending.pop(0)
            if not self.pending:
                self.state.prompt_count += 1  # the prompt after the last line
                if self.roundtime and not self.waited:
                    self.state.roundtime = self.state.server_time + self.roundtime
            return piece
        if timeout:
            time.sleep(min(timeout, 0.02))
        return None

    def waitrt(self):
        self.waited = True
        self.state.server_time = self.state.roundtime  # the roundtime ran out
        self.pending.extend(self.after_roundtime)


def test_ask_ends_its_windows_at_the_prompt_and_skips_the_tail_without_a_roundtime():
    # #248: a 3 s window and a 1.5 s tail held every command 4.5 s after
    # an answer that came in a tenth. The prompt closes the answer, a
    # quiet quarter second confirms it, and with no roundtime nothing
    # can land later.
    handle = PromptedHandle(["You get a cotton rag from inside your canvas sack.\n"])
    started = time.monotonic()
    answer = probe.ask(handle, "get my rag", 3.0, 1.5)
    assert answer == "You get a cotton rag from inside your canvas sack."
    assert time.monotonic() - started < 1.0
    assert handle.waited is False


def test_ask_with_a_roundtime_still_collects_what_lands_at_its_end():
    handle = PromptedHandle(
        ["You wander around and poke your fingers about.\n"],
        after_roundtime=["You forage around but find nothing.\n"],
        roundtime=6,
    )
    started = time.monotonic()
    answer = probe.ask(handle, "forage grass", 3.0, 1.5)
    assert "find nothing" in answer and handle.waited is True
    assert time.monotonic() - started < 1.5  # two quiet stretches, not 4.5 s


def test_an_unrelated_prompt_right_after_the_send_does_not_cut_the_answer():
    # A bite or another player's arrival comes with a prompt too; the
    # quiet stretch after it is broken by the answer, so both are read.
    handle = PromptedHandle(
        ["The clerk counts out 6 silver Kronars and hands them over.\n"],
        intruder="Rikkie just arrived.\n",
    )
    answer = probe.ask(handle, "withdraw 6 silver", 3.0, 1.5)
    assert answer.splitlines() == [
        "Rikkie just arrived.",
        "The clerk counts out 6 silver Kronars and hands them over.",
    ]


def test_a_fake_without_a_prompt_count_waits_the_windows_as_before():
    handle = FakeHandle(["You wander around and poke your fingers about.\n"])
    started = time.monotonic()
    probe.ask(handle, "forage grass", 0.3, 0.2)
    assert time.monotonic() - started >= 0.45


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


class StreamedHandle(FakeHandle):
    """Pieces tagged with their stream, filtered the way a handle's get()
    filters: only the streams asked for come back."""

    def get(self, timeout=None, streams=("",)):
        while self.pending:
            stream, piece = self.pending.pop(0)
            if streams is None:
                return stream, piece
            if stream in streams:
                return piece
        return None


def test_collect_reads_the_combat_stream_with_the_story():
    # Every swing and kill line of the 2026-09-12 hunt arrived inside
    # <pushStream id="combat"/>; a story-only read saw none of them.
    handle = StreamedHandle(
        [
            ("combat", "< You slice a handaxe at a rat.\n"),
            ("combat", "The rat falls to the ground and lies still.\n"),
            ("", "[Roundtime 6 sec.]\n"),
            ("thoughts", "Someone thinks aloud.\n"),
        ]
    )
    answer = probe.ask(handle, "attack", 0.1, 0)
    assert "lies still" in answer
    assert "[Roundtime 6 sec.]" in answer
    assert "thinks aloud" not in answer


class RefusingHandle(FakeHandle):
    """The game refuses the first `refusals` sends with "...wait 1
    seconds." — a roundtime with a fraction of a second left that no
    prompt stamp could show (#251) — and takes the next."""

    def __init__(self, answers, refusals=1):
        super().__init__(answers)
        self.refusals = refusals
        self.slept = []

    def put(self, command):
        self.sent.append(command)
        if len(self.sent) <= self.refusals:
            self.pending = ["...wait 1 seconds.\n"]
        else:
            self.pending = list(self.answers)

    def sleep(self, seconds):
        self.slept.append(seconds)


def test_ask_resends_a_command_the_game_refused_inside_a_roundtime():
    # Captured 2026-09-20: INVOKE's one-second roundtime ended in the
    # second the prompt showed, the CAST went out and "...wait 1
    # seconds." came back as its answer — the spell never cast.
    handle = RefusingHandle(["You gesture.\n"])
    assert probe.ask(handle, "cast", 0.02, 0) == "You gesture."
    assert handle.sent == ["cast", "cast"]
    assert len(handle.slept) == 1 and 1 <= handle.slept[0] <= 1.5


def test_ask_gives_the_refusal_back_after_three_resends():
    handle = RefusingHandle(["You gesture.\n"], refusals=10)
    assert probe.ask(handle, "cast", 0.02, 0) == "...wait 1 seconds."
    assert handle.sent == ["cast"] * (probe.WAIT_RETRIES + 1)
