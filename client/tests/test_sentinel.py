"""The sentinel script under a fake handle — these tests are the manual
for what ;sentinel does with a line (#276): a stranger's whisper rings
three bells, echoes SENTINEL: and starts the grace; `;sentinel ok` ends
it; an unanswered grace tells ;train to return and QUITs; an NPC's
canned line, a line naming a player present and the room's boilerplate
pass in silence; a new line lands in the Attention dock once. The cast
is synthetic."""

import importlib.util
import pathlib
import queue
from types import SimpleNamespace

REPO = pathlib.Path(__file__).parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "sentinel_script", REPO / "scripts/sentinel.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sentinel = _load()
sentinel.BELL_GAP = 0.0


class Handle:
    """The handle API the watch touches: a queue of (stream, text)
    pieces, typed ;sentinel words, the echoes and emits, the other
    scripts' state."""

    def __init__(self, players=()):
        self.state = SimpleNamespace(name="Lanival", room_players=list(players))
        self.lines = queue.Queue()
        self.words = queue.Queue()
        self.echoed = []
        self.emitted = []
        self.sent = []
        self.told = []
        self.killed = []
        self.running = set()

    def get(self, timeout=None, streams=("",)):
        try:
            return self.lines.get_nowait()
        except queue.Empty:
            return None

    def command(self, timeout=None):
        try:
            return self.words.get_nowait()
        except queue.Empty:
            # The loop test: once every queued line is read, "return".
            if getattr(self, "return_when_drained", False) and self.lines.empty():
                self.return_when_drained = False
                return "return"
            return None

    def echo(self, text):
        self.echoed.append(text)

    def emit(self, text, stream):
        self.emitted.append((stream, text))

    def put(self, command, cleanup=False):
        self.sent.append(command)

    def sleep(self, seconds):
        pass

    def is_running(self, name):
        return name in self.running

    def tell(self, name, line):
        self.told.append((name, line))
        self.running.discard(name)
        return True

    def kill(self, name):
        self.killed.append(name)
        self.running.discard(name)

    @property
    def bells(self):
        return sum(1 for stream, _ in self.emitted if stream == "bell")

    @property
    def attention(self):
        return [text for stream, text in self.emitted if stream == "attention"]


def _watch(handle, settings=None, own=("Lanival", "Sable")):
    from client.game.novelty import Novelty

    return sentinel.Watch(handle, dict(settings or {}), Novelty(), list(own))


def test_a_strangers_whisper_rings_three_bells_and_starts_the_grace():
    s = Handle()
    watch = _watch(s, {"sentinel_grace_minutes": 2})
    watch.handle("whispers", 'Uthmor whispers to you, "you there?"', 100.0)
    assert s.bells == 3
    assert any("SENTINEL: whisper: Uthmor whispers" in text for text in s.echoed)
    assert any(";sentinel ok within 2 min" in text for text in s.echoed)
    assert watch.grace_until == 100.0 + 120
    assert s.attention == ['! whisper: Uthmor whispers to you, "you there?"\n']
    # A second alert inside the grace rings again but keeps the deadline.
    watch.handle("", "Uthmor waves to you.", 130.0)
    assert s.bells == 6
    assert watch.grace_until == 220.0


def test_ok_ends_the_grace_and_quiet_keeps_the_dock_filling_without_bells():
    s = Handle()
    watch = _watch(s)
    watch.handle("", 'Uthmor says to you, "Hello?"', 10.0)
    assert watch.grace_until is not None
    assert watch.command("ok", 20.0) is False
    assert watch.grace_until is None
    assert watch.command("quiet 5", 30.0) is False
    watch.handle("", 'Uthmor says to you, "Hello?"', 40.0)
    assert s.bells == 3  # only the first alert rang
    assert watch.grace_until is None
    assert len(s.attention) == 2
    assert watch.command("return", 50.0) is True


def test_an_unanswered_grace_returns_the_trainer_and_quits(monkeypatch):
    s = Handle()
    s.running.add("train")
    watch = _watch(s, {"sentinel_grace_minutes": 1})
    monkeypatch.setattr(sentinel.time, "time", lambda: 1000.0)
    watch.handle("", "Uthmor pokes you.", 0.0)
    assert watch.check_grace(30.0) is False  # still inside the minute
    assert watch.check_grace(61.0) is True
    assert s.told == [("train", "return")]
    assert s.sent == ["quit"]
    assert s.killed == []


def test_the_grace_ends_without_a_logout_when_the_setting_says_so():
    s = Handle()
    watch = _watch(s, {"sentinel_logout": False})
    watch.handle("", "Uthmor pokes you.", 0.0)
    assert watch.check_grace(10_000.0) is False
    assert s.sent == []
    assert any("staying" in text for text in s.echoed)
    assert watch.grace_until is None


def test_npcs_own_characters_players_present_and_boilerplate_pass_in_silence():
    s = Handle(players=["Uthmor"])
    watch = _watch(s)
    for stream, line in (
        (
            "",
            'A fair-skinned priestess says to you, "Are you lost?  Just NOD at me if so."',
        ),
        ("", 'Sable says to you, "Hello?"'),  # the operator's own character
        ("", "Uthmor swings a sword at a rat."),  # a player present, their business
        ("", "Obvious paths: north, south."),
        ("combat", "Uthmor whispers to you, hidden in the combat stream."),
        ("logons", "Uthmor has logged on."),
    ):
        watch.handle(stream, line, 5.0)
    watch.judge(10.0)
    assert s.bells == 0
    assert s.echoed == []
    # The NPC's canned line and your own character's are news once (the
    # dock, no bell); the player's swing and the exits are not even that.
    assert len(s.attention) == 2
    assert not any("swings" in text or "Obvious" in text for text in s.attention)


def test_a_new_line_lands_in_the_dock_once_and_a_hidden_command_alerts():
    s = Handle()
    watch = _watch(s)
    watch.handle("", "A stranger looks at you oddly.", 1.0)
    watch.handle("", "A stranger looks at you oddly.", 2.0)
    watch.judge(10.0)
    assert s.attention == ["A stranger looks at you oddly.\n"]
    assert s.bells == 0
    watch.handle("", 'Uthmor says, "J_u_M_p"', 3.0)
    assert s.bells == 3
    assert any("hidden command" in text for text in s.echoed)


def test_spam_rings_the_bells_but_never_starts_the_grace():
    # Too weak a sign to end a session on: the first evening's false
    # alarms were the character's own lines, now left out of the
    # windows; a stranger's flood still rings, and only rings.
    s = Handle()
    watch = _watch(s)
    for i in range(6):
        watch.handle("", "A rat squeaks loudly.", float(i))
    watch.judge(20.0)
    assert s.bells == 3
    assert watch.grace_until is None
    assert any("SENTINEL: spam:" in text for text in s.echoed)
    assert not any(";sentinel ok within" in text for text in s.echoed)


def test_a_staff_broadcast_and_an_arrival_ring_once_without_a_grace():
    s = Handle()
    watch = _watch(s)
    watch.handle("ooc", "TWEET:  The war drums are sounding. #drprime", 1.0)
    assert s.bells == 1
    assert watch.grace_until is None
    assert s.attention[-1].startswith("broadcast: TWEET")
    s.state.room_players = ["Uthmor", "Sable"]
    watch.watch_players(2.0)
    assert s.bells == 2
    assert s.attention[-1] == "arrived: Uthmor\n"  # Sable is the operator's own
    assert watch.grace_until is None


def test_the_rooms_description_on_either_side_of_its_room_frame_is_not_news():
    # The description and the room frame arrive in either order
    # (client/ui/roomids.py), so a story line is judged only once the
    # window has passed, against the frames on both sides of it.
    s = Handle()
    watch = _watch(s)
    watch.handle("", "A wide green sweeps toward the river.", 9.5)  # before
    watch.handle("room", "123\tThe Crossing, Town Green", 10.0)
    watch.handle("", "Oaks line the walk here.", 10.5)  # after
    watch.judge(10.6)
    assert watch.pending  # too soon to judge anything
    watch.judge(13.0)
    assert s.attention == []
    watch.handle("", "A wide green sweeps toward the river.", 20.0)
    watch.judge(30.0)
    assert s.attention == ["A wide green sweeps toward the river.\n"]


def test_a_compass_frame_marks_an_arrival_and_a_passer_by_is_judged_as_present():
    # The first evening: a walk pacing the same rooms leaked their
    # descriptions (only a changed room sends a room frame; the compass
    # comes every move), and a passer-by's line was judged after they
    # had left the room.
    s = Handle()
    watch = _watch(s)
    watch.handle("compass", "n s\n", 10.0)
    watch.handle("", "A wide green sweeps toward the river.", 10.4)
    watch.judge(13.0)
    assert s.attention == []
    s.state.room_players = ["Uthmor"]
    watch.handle("", "Uthmor stomps north.", 20.0)
    s.state.room_players = []  # gone before the judgement
    watch.judge(25.0)
    assert s.attention == []


def test_a_creatures_line_and_an_answer_to_our_own_command_are_never_spam():
    s = Handle()
    s.state.room_creatures = ["cougar", "second cougar"]
    watch = _watch(s)
    for i in range(6):
        watch.handle("", "A cougar's rear legs dig at the ground.", float(i))
    watch.judge(10.0)
    assert s.bells == 0 and s.attention == []  # the room's creature: its business
    s.state.room_creatures = []
    for i in range(6):
        watch.handle("sent", "disarm my crate identify\n", 20.0 + i)
        watch.handle("", "Crush what?", 20.5 + i)
    watch.judge(40.0)
    assert s.bells == 0
    assert s.attention == ["Crush what?\n"]  # news once, never spam


def test_pieces_are_glued_into_lines_per_stream():
    s = Handle()
    watch = _watch(s)
    assert watch.lines_from("", "Uthmor whispers to ") == []
    assert watch.lines_from("thoughts", "chatter\n") == ["chatter"]
    assert watch.lines_from("", 'you, "hi"\r\nNext') == ['Uthmor whispers to you, "hi"']
    assert watch.lines_from("", " line\n") == ["Next line"]


def test_the_loop_reads_pieces_and_words_until_told_to_return():
    s = Handle()
    watch = _watch(s)
    s.lines.put(("", 'Uthmor whispers to you, "there?"\n'))
    s.words.put("status")
    s.return_when_drained = True
    watch.loop()
    assert s.bells == 3
    assert any("alert(s)" in text for text in s.echoed)


def test_the_alert_command_gets_the_alert_as_its_last_argument(monkeypatch):
    calls = []

    class Popen:
        def __init__(self, args, **kwargs):
            calls.append(args)

    monkeypatch.setattr(sentinel.subprocess, "Popen", Popen)
    s = Handle()
    watch = _watch(s, {"alert_command": 'notify "Revenant"'})
    watch.handle("", "Uthmor waves to you.", 1.0)
    assert calls == [
        ["notify", "Revenant", "gesture: Uthmor waves to you."]
    ] or calls == [["notify", '"Revenant"', "gesture: Uthmor waves to you."]]


def test_a_failing_alert_command_is_said_once_and_the_bells_still_ring(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("no such program")

    monkeypatch.setattr(sentinel.subprocess, "Popen", boom)
    s = Handle()
    watch = _watch(s, {"alert_command": "nosuchprogram"})
    watch.handle("", "Uthmor waves to you.", 1.0)
    watch.handle("", "Uthmor pokes you.", 2.0)
    assert s.bells == 6
    assert sum("alert_command failed" in text for text in s.echoed) == 1
