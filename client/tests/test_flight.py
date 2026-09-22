"""The shared escape (client/game/flight.py, #285): stand when seated,
retreat twice and move through the type-ahead, the caller's step before
the compass exits, judged by the room changing."""

from types import SimpleNamespace

from client.game import flight


class Handle:
    """A room with hostiles who re-advance after every retreat; the moves
    in `passable` change the room, the others fail (a climb for footing)."""

    def __init__(self, passable=("nw",), posture="IconSTANDING", compass=("nw",)):
        self.passable = set(passable)
        self.sent, self.echoed, self.emitted = [], [], []
        self.state = SimpleNamespace(
            room_uid=100,
            room_title="[Outside the Western Gate]",
            compass=list(compass),
            hostiles={"1": True},
            indicator={posture: "y"} if posture else {},
        )

    def put(self, command):
        self.sent.append(command)
        if command in self.passable:
            self.state.room_uid = 101
            self.state.room_title = "[Inside the Gate]"
            self.state.hostiles = {}

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass

    def echo(self, text):
        self.echoed.append(text)

    def emit(self, text, stream):
        self.emitted.append((text, stream))


def test_the_moves_are_the_callers_steps_then_the_exits_then_out():
    state = SimpleNamespace(compass=["nw", "e"])
    assert flight.moves(state, ["climb wall"]) == ["climb wall", "nw", "e", "out"]
    assert flight.moves(SimpleNamespace(compass=[])) == ["out"]


def test_a_seated_character_stands_first_and_a_standing_one_does_not():
    seated = Handle(posture="IconSITTING")
    assert flight.flee(seated) is True
    assert seated.sent == ["stand", "retreat", "retreat", "nw"]
    standing = Handle()
    flight.flee(standing)
    assert standing.sent == ["retreat", "retreat", "nw"]
    unknown = Handle(posture=None)
    flight.flee(unknown)
    assert unknown.sent[0] == "retreat"


def test_a_failed_climb_gives_way_to_the_exit():
    # #286: the climb never changed the room; the next burst takes the exit.
    handle = Handle(passable=("nw",))
    assert flight.flee(handle, preferred=["climb wall"]) is True
    assert handle.sent == [
        "retreat",
        "retreat",
        "climb wall",
        "retreat",
        "retreat",
        "nw",
    ]


def test_eight_held_bursts_report_failure():
    handle = Handle(passable=())
    assert flight.flee(handle, preferred=["climb wall"]) is False
    assert handle.sent.count("retreat") == 16
    assert handle.sent[2::3] == [
        "climb wall",
        "nw",
        "out",
        "climb wall",
        "nw",
        "out",
        "climb wall",
        "nw",
    ]


def test_react_says_rings_and_reports():
    handle = Handle()
    assert flight.react(handle, "perform") is True
    assert handle.echoed[0] == "perform: hostiles here — getting away"
    assert handle.echoed[-1] == "perform: clear of them — [Inside the Gate]"
    assert ("", "bell") in handle.emitted
    held = Handle(passable=())
    assert flight.react(held, "perform", attempts=2) is False
    assert "could not get clear in 2 tries" in held.echoed[-1]


def test_to_safety_walks_with_the_invaded_rooms_avoided():
    walks = []

    def walk(s, db, goals, describe="", avoid=()):
        walks.append((set(goals), set(avoid)))
        return True

    assert flight.to_safety(Handle(), None, walk, [748], avoid=[6046]) is True
    assert walks == [({748}, {6046})]
    assert flight.to_safety(Handle(), None, walk, []) is False
