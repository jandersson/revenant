"""A helper character for a task — the teacher `;train` logs in for a
class and out after it (the operator, 2026-09-22: "log in Fallanor
when Cecil needs a class and log him out when he moves on").

A task naming a `helper` (one of the operator's own characters whose
account password the OS keychain holds) has that character's session
found in the registry or spawned without a window, walked to the
task's `helper_room` (else where the student stands) by `;go2`,
started on `helper_script` with `helper_args` — `;teach scholarship
to cecil` — and, when the task ends, given the script's return word;
a session this loop spawned is logged out through `;logout` (QUIT
from inside, the policy refuses one from outside) unless the next
task names the same helper, so two classes in a row share one login.
The spawn tells the session who spawned it and on which port
(`REVENANT_SPAWNED_BY`, `REVENANT_PARENT_PORT`, #296): its registry
row carries the mark, so a later loop treats the helper an earlier
loop left behind as its own to log out, and the session itself logs
out once the spawning session's port has refused two heartbeats in a
row — a teacher offering a class to nobody after the student's
session was relaunched (2026-09-23) is gone within a minute or two.
An account plays one character at a time, so a helper sharing its
account with a logged-in character has that one `;logout` first
(Riphik and Westan). A task with no script or commands of the
student's own lasts while the helper's script runs (the session's
`scripts` state) — Riphik's `;empath cecil` after a hunt — and ends
without a return word that would start the script again. A task whose
`helper_after` is "stay" leaves the helper logged in for the next one
(Riphik between heals; the session answers the idle warning itself).
A helper running its own `;train` is busy (#470): its task is
skipped, said, rather than two loops driving one character.
Every line to the helper goes through the wire tagged "train", so its
window reads `>> [train] ...`. A helper that cannot be had — no
account cached for the name, no password in the keychain, a session
that never comes up, a walk that never arrives — is said, and the
task runs without it (the student LISTENs to no one, and ends on its
time budget). Everything that touches a socket or a process goes
through the `io` object `scripts/train.py` provides, so the decisions
here are tested dry.
"""

from time import monotonic

from client.engine.wire import EXTERNAL_MARK

ORIGIN = "train"
DEFAULT_SCRIPT = "teach"
ARRIVAL_SECONDS = 180  # the helper's walk to the room
KNOWN_SECONDS = 30  # a fresh login's parser learning its room before ;go2
SETTLE_SECONDS = 3  # after a script start or return, before the next line
LOGOUT_SECONDS = 90  # the account's other character's ;logout
# A helper running one of these drives itself: a task wanting it is
# skipped (#470, the operator's option 1, 2026-10-04).
BUSY_SCRIPTS = ("train",)


class Helper:
    """A helper's live session: its name, port, and whether this loop
    spawned it (and so logs it out)."""

    def __init__(self, name, port, spawned):
        self.name = name
        self.port = port
        self.spawned = spawned


def spec_of(task):
    """{"name", "script", "args", "room"} for a task that names a
    helper, else None."""
    name = str(task.get("helper") or "").strip()
    if not name:
        return None
    return {
        "name": name,
        "script": str(task.get("helper_script") or DEFAULT_SCRIPT).strip(),
        "args": [str(arg) for arg in (task.get("helper_args") or []) if str(arg)],
        "room": str(task.get("helper_room") or "").strip(),
    }


def tagged(command):
    """The wire line for a command from this loop: `\\x1etrain\\t<command>`."""
    mark = EXTERNAL_MARK.decode() if isinstance(EXTERNAL_MARK, bytes) else EXTERNAL_MARK
    return f"{mark}{ORIGIN}\t{command}"


def find_session(sessions, name):
    """The port of a registered session playing `name`, or None."""
    for entry in sessions or []:
        if str(entry.get("character") or "").lower() == name.lower():
            return entry.get("port")
    return None


def keeps(next_task, name):
    """True when the task after this one names the same helper — the
    session stays up between them."""
    spec = spec_of(next_task or {})
    return bool(spec) and spec["name"].lower() == name.lower()


def spawned_by_loop(sessions, name):
    """True when the registered session playing `name` was spawned by
    a training loop (its row's `spawned_by`, #296) — an earlier loop's
    helper, this loop's to log out."""
    for entry in sessions or []:
        if str(entry.get("character") or "").lower() == name.lower():
            return str(entry.get("spawned_by") or "") == ORIGIN
    return False


def account_holder(io, sessions, name, account):
    """The other character with a live session on `account`, or None:
    an account plays one character at a time (Riphik and Westan share
    one)."""
    for entry in sessions or []:
        other = str(entry.get("character") or "")
        if other and other.lower() != name.lower() and io.account_for(other) == account:
            return other
    return None


def running(io, helper, script):
    """True while `script` runs in the helper's session, False once it
    has ended, None when the session does not say (an older session
    without `scripts` in its state, or no answer)."""
    names = io.scripts_of(helper.port)
    if names is None:
        return None
    return script.lower() in {str(n).lower() for n in names}


def busy(io, name):
    """The script that keeps the logged-in helper `name` busy — its own
    `;train` (#470) — or None when it is free, logged out, or its
    session does not say."""
    port = find_session(io.sessions(), name)
    if not port:
        return None
    names = {str(n).lower() for n in io.scripts_of(port) or []}
    return next((script for script in BUSY_SCRIPTS if script in names), None)


def ensure(io, name, echo, spawned_before=(), own_port=None):
    """The helper's session — found, or spawned off the keychain — as a
    Helper; None, said, when it cannot be had. A session found that
    this loop spawned for an earlier task (`spawned_before`), or that
    any loop spawned (its registry row's `spawned_by`, #296: the
    teacher an earlier loop left behind when its session was
    relaunched), stays the loop's to log out. `own_port` is this loop's
    session, given to the spawn so the helper can tell when it is
    gone."""
    sessions = io.sessions()
    port = find_session(sessions, name)
    if port:
        mine = name.lower() in {str(n).lower() for n in spawned_before}
        return Helper(name, port, spawned=mine or spawned_by_loop(sessions, name))
    account = io.account_for(name)
    if not account:
        echo(f"train: no account cached for {name} — log {name} in once by hand")
        return None
    if not io.has_password(account):
        echo(
            f"train: {name}'s account password is not in the keychain — log "
            f"{name} in once with Remember me"
        )
        return None
    if other := account_holder(io, sessions, name, account):
        # The account plays one character at a time: the other logs out
        # through its own ;logout first rather than being cut off by
        # the login (the operator, 2026-09-27: "it's cool if you drop
        # Westan" for Riphik).
        echo(f"train: logging {other} out — {name} shares the account")
        io.send(find_session(sessions, other), tagged(";logout"))
        deadline = io.now() + LOGOUT_SECONDS
        while find_session(io.sessions(), other) and io.now() < deadline:
            io.sleep(2)
        if find_session(io.sessions(), other):
            echo(f"train: {other} did not log out — the task goes on without {name}")
            return None
        io.sleep(SETTLE_SECONDS)
    echo(f"train: logging {name} in")
    port = io.spawn(name, account, own_port)
    if port is None:
        echo(f"train: {name}'s session did not come up")
        return None
    return Helper(name, port, spawned=True)


def bring(io, helper, target, echo, seconds=ARRIVAL_SECONDS):
    """The helper brought to `target`: its room waited for first (a
    session just logged in answers `;go2` with "current room unknown
    yet", 2026-09-22), `;go2 <target>` sent unless it stands there
    already, the arrival read off its state until it is the target's
    map id. True there; False, said, when the walk did not end there."""
    known = io.now() + KNOWN_SECONDS
    room = io.room_of(helper.port)
    while room is None and io.now() < known:
        io.sleep(2)
        room = io.room_of(helper.port)
    if room == str(target):
        return True
    io.send(helper.port, tagged(f";go2 {target}"))
    deadline = io.now() + seconds
    while io.now() < deadline:
        if io.room_of(helper.port) == str(target):
            return True
        io.sleep(2)
    echo(f"train: {helper.name} did not reach room {target} in {seconds} s")
    return False


def start(io, helper, script, args):
    """The helper's script started: `;teach scholarship to cecil`."""
    io.send(helper.port, tagged(f";{script} {' '.join(args)}".rstrip()))
    io.sleep(SETTLE_SECONDS)


def finish(io, helper, script, keep, echo, ended=False):
    """The helper's script given its return word — unless it `ended`
    on its own, when `;<script> return` would start it again with
    "return" for its argument; a session this loop spawned logged out
    unless `keep` (the next task wants it too)."""
    if not ended:
        io.send(helper.port, tagged(f";{script} return"))
        io.sleep(SETTLE_SECONDS)
    if helper.spawned and not keep:
        echo(f"train: logging {helper.name} out")
        io.send(helper.port, tagged(";logout"))
        return True
    return False


class SessionIO:
    """What this module needs of the world, for ;train and ;heal alike:
    the registry, the login cache and keychain, the launcher's spawn,
    the wire, the map, and the calling script's stop-aware sleep."""

    def __init__(self, s, db=None):
        self.s = s
        self.db = db

    def sessions(self):
        from client.engine.registry import running_sessions

        return running_sessions()

    def account_for(self, name):
        from client.engine.login import account_for_character, load_login_defaults

        return account_for_character(load_login_defaults(), name)

    def has_password(self, account):
        from client.engine.login import keychain_password

        return keychain_password(account) is not None

    def own_port(self):
        """This loop's session port, off the registry by the character's
        name — the parent a spawned helper watches (#296)."""
        name = getattr(self.s.state, "name", None)
        return find_session(self.sessions(), name) if name else None

    def spawn(self, name, account, parent_port=None):
        from client.engine.launch import (
            DEFAULT_HOST,
            get_free_port,
            spawn_session,
            wait_for_session,
        )

        port = get_free_port(DEFAULT_HOST)
        process = spawn_session(
            DEFAULT_HOST,
            port,
            name,
            key=None,
            account=account,
            spawned_by=ORIGIN,
            parent_port=parent_port,
        )
        try:
            wait_for_session(process, DEFAULT_HOST, port, timeout=90)
        except SystemExit:
            return None
        return port

    def send(self, port, line):
        from client.engine.launch import DEFAULT_HOST
        from client.engine.wire import send_line

        return send_line(DEFAULT_HOST, port, line)

    def room_of(self, port):
        from client.engine.launch import DEFAULT_HOST
        from client.engine.wire import request_state

        try:
            state = request_state(DEFAULT_HOST, port, ["room"], ORIGIN)
        except OSError:
            return None
        uid = (state.get("room") or {}).get("uid") if isinstance(state, dict) else None
        if not uid or self.db is None:
            return None
        room = self.db.room_by_uid(uid)
        return str(room) if room is not None else None

    def scripts_of(self, port):
        """The scripts running in the session on `port`, or None when
        it does not say."""
        from client.engine.launch import DEFAULT_HOST
        from client.engine.wire import request_state

        try:
            state = request_state(DEFAULT_HOST, port, ["scripts"], ORIGIN)
        except OSError:
            return None
        names = state.get("scripts") if isinstance(state, dict) else None
        return list(names) if isinstance(names, list) else None

    def now(self):
        return monotonic()

    def sleep(self, seconds):
        self.s.sleep(seconds)
