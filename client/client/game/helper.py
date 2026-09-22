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
Every line to the helper goes through the wire tagged "train", so its
window reads `>> [train] ...`. A helper that cannot be had — no
account cached for the name, no password in the keychain, a session
that never comes up, a walk that never arrives — is said, and the
task runs without it (the student LISTENs to no one, and ends on its
time budget). Everything that touches a socket or a process goes
through the `io` object `scripts/train.py` provides, so the decisions
here are tested dry.
"""

from client.engine.wire import EXTERNAL_MARK

ORIGIN = "train"
DEFAULT_SCRIPT = "teach"
ARRIVAL_SECONDS = 180  # the helper's walk to the room
KNOWN_SECONDS = 30  # a fresh login's parser learning its room before ;go2
SETTLE_SECONDS = 3  # after a script start or return, before the next line


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


def ensure(io, name, echo, spawned_before=()):
    """The helper's session — found, or spawned off the keychain — as a
    Helper; None, said, when it cannot be had. A session found that
    this loop spawned for an earlier task (`spawned_before`) stays
    the loop's to log out."""
    port = find_session(io.sessions(), name)
    if port:
        mine = name.lower() in {str(n).lower() for n in spawned_before}
        return Helper(name, port, spawned=mine)
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
    echo(f"train: logging {name} in")
    port = io.spawn(name, account)
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


def finish(io, helper, script, keep, echo):
    """The helper's script given its return word; a session this loop
    spawned logged out unless `keep` (the next task wants it too)."""
    io.send(helper.port, tagged(f";{script} return"))
    io.sleep(SETTLE_SECONDS)
    if helper.spawned and not keep:
        echo(f"train: logging {helper.name} out")
        io.send(helper.port, tagged(";logout"))
        return True
    return False
