"""A helper character for a task — these tests are the manual. The
teacher's session is found in the registry or spawned off the
keychain, walked to the room and started on its script through the
wire tagged "train", returned when the task ends, and logged out when
this loop spawned it and the next task does not keep it (2026-09-22).
Every socket and process is behind a fake io; nothing here connects."""

from client.game import helper


class IO:
    """The world as helper.py sees it: a registry, a login cache, a
    keychain, a spawner, a wire, a clock."""

    def __init__(
        self, sessions=(), accounts=None, passwords=(), spawn_port=4250, rooms=()
    ):
        self.registry = list(sessions)
        self.accounts = accounts or {}
        self.passwords = set(passwords)
        self.spawn_port = spawn_port
        self.rooms = list(rooms)  # the helper's room per poll, the last repeating
        self.sent = []
        self.spawned = []
        self.clock = 0.0

    def sessions(self):
        return self.registry

    def account_for(self, name):
        return self.accounts.get(name)

    def has_password(self, account):
        return account in self.passwords

    def spawn(self, name, account):
        self.spawned.append((name, account))
        return self.spawn_port

    def send(self, port, line):
        self.sent.append((port, line))
        return True

    def room_of(self, port):
        if len(self.rooms) > 1:
            return self.rooms.pop(0)
        return self.rooms[0] if self.rooms else None

    def now(self):
        return self.clock

    def sleep(self, seconds):
        self.clock += seconds


TASK = {
    "name": "class",
    "helper": "Fallanor",
    "helper_args": ["parry ability", "to", "cecil"],
    "helper_room": "7890",
}


def test_a_task_names_its_helper_and_the_lines_are_tagged():
    assert helper.spec_of(TASK) == {
        "name": "Fallanor",
        "script": "teach",
        "args": ["parry ability", "to", "cecil"],
        "room": "7890",
    }
    assert helper.spec_of({"name": "hunt"}) is None
    assert helper.tagged(";go2 7890") == "\x1etrain\t;go2 7890"
    assert (
        helper.find_session([{"port": 4243, "character": "fallanor"}], "Fallanor")
        == 4243
    )
    assert (
        helper.find_session([{"port": 4242, "character": "Cecil"}], "Fallanor") is None
    )
    assert helper.keeps({"helper": "fallanor"}, "Fallanor")
    assert not helper.keeps({"name": "hunt"}, "Fallanor")
    assert not helper.keeps(None, "Fallanor")


def test_a_running_session_is_used_and_never_logged_out():
    said = []
    io = IO(sessions=[{"port": 4243, "character": "Fallanor"}])
    active = helper.ensure(io, "Fallanor", said.append)
    assert (active.port, active.spawned) == (4243, False)
    assert not io.spawned
    assert helper.finish(io, active, "teach", keep=False, echo=said.append) is False
    assert io.sent == [(4243, "\x1etrain\t;teach return")]


def test_a_missing_session_is_spawned_off_the_keychain_and_logged_out_after():
    said = []
    io = IO(
        accounts={"Fallanor": "TESTACCT"},
        passwords={"TESTACCT"},
        rooms=[None, "1901", "1901", "7890"],  # the login's room unknown at first
    )
    active = helper.ensure(io, "Fallanor", said.append)
    assert (active.port, active.spawned) == (4250, True)
    assert io.spawned == [("Fallanor", "TESTACCT")]
    assert "logging Fallanor in" in said[-1]
    assert helper.bring(io, active, "7890", said.append)
    assert io.sent[0] == (4250, "\x1etrain\t;go2 7890")
    # Already in the room: no walk sent at all.
    there = IO(rooms=["7890"])
    assert helper.bring(there, active, "7890", said.append)
    assert there.sent == []
    helper.start(io, active, "teach", ["parry ability", "to", "cecil"])
    assert io.sent[-1] == (4250, "\x1etrain\t;teach parry ability to cecil")
    assert helper.finish(io, active, "teach", keep=True, echo=said.append) is False
    assert helper.finish(io, active, "teach", keep=False, echo=said.append) is True
    assert io.sent[-1] == (4250, "\x1etrain\t;logout")
    assert "logging Fallanor out" in said[-1]
    # A session found later that this loop spawned is still the loop's.
    found = IO(sessions=[{"port": 4250, "character": "Fallanor"}])
    again = helper.ensure(found, "Fallanor", said.append, spawned_before={"fallanor"})
    assert again.spawned is True


def test_what_cannot_be_had_is_said_and_the_task_goes_on_alone():
    said = []
    assert helper.ensure(IO(), "Fallanor", said.append) is None
    assert "no account cached for Fallanor" in said[-1]
    assert (
        helper.ensure(IO(accounts={"Fallanor": "TESTACCT"}), "Fallanor", said.append)
        is None
    )
    assert "password is not in the keychain" in said[-1]
    io = IO(accounts={"Fallanor": "TESTACCT"}, passwords={"TESTACCT"}, spawn_port=None)
    assert helper.ensure(io, "Fallanor", said.append) is None
    assert "did not come up" in said[-1]
    # A walk that never arrives is said; the caller decides.
    slow = IO(rooms=["1901"])
    late = helper.Helper("Fallanor", 4250, True)
    assert helper.bring(slow, late, "7890", said.append, seconds=10) is False
    assert "did not reach room 7890" in said[-1]
