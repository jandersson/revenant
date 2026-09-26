"""The script engine: player-written Python running inside the session.

A script is a .py file in the scripts directory defining `main(s)`. It runs
in its own thread with `s` as its handle on the game:

    s.put("look")                      # send a command (echoed to front ends)
    line = s.get(timeout=5)            # next main-stream line, None on timeout
    line = s.waitfor(r"Obvious paths", timeout=10)
    s.echo("done!")                    # front-end-only output
    s.emit("psst", "thoughts")         # front-end output on a chosen stream
    line = s.command(timeout=0)        # next user line (;name <line>), None if none
    s.sleep(2)                         # stop-aware sleep
    s.state                            # the session's XMLData (indicators etc.)
    s.dead                             # True while the character is dead
    s.args                             # arguments from `;run name arg1 arg2`
    s.run("athletics", ["list"])       # start another script; False if it can't
    s.is_running("athletics")          # is that script's thread alive?
    s.tell("hunt", "stop")             # hand it a line, as ;hunt stop would
    s.kill("athletics")                # stop it (;train orchestrates this way)
    s.flag("ended", r"You stop playing")  # watch every line for a pattern (#279)
    line = s.flagged("ended")          # the line once one matched (and cleared), else None

Scripts are controlled from any attached front end with ;-commands:
;list, ;help [name], ;run <name> [args], ;stop <name|all> (;k and
;kill are lich-style aliases, and a unique prefix of a running
script's name is enough: ;k mech), or ;<name> [args] as shorthand for
;run. ;help prints a script's module docstring — write them as the
user manual. Typing ;<name> <line> while <name> is running delivers
<line> to it via s.command(); the lich chat shorthands (;chat, ;reply,
;who, ...) route to the lnet script.

Every start loads the script file fresh from disk, and reloads the
client/ helper modules scripts lean on (RELOADABLE_MODULES: probe,
walker, mapdb, inventory, profile, ...) when their files changed since they were
imported — so a fix in the walker reaches a running session through
;stop go2 and ;go2, the way lich's common scripts do (#138). A reload
is a fresh copy of the module, never a re-execution in place: a
script already running keeps every function it imported, with the
globals those functions were written against, and the next start gets
the new code (#181 — an in-place reload once left ;hunt's old `walk`
calling the walker's new three-value helper). Modules holding the
socket, the parser, or threads never reload; that is ;reexec's job.
A script that crashes is remembered (`s.crashed(name)`) so a driver
like ;train can tell a crash from a clean exit.
"""

import ast
import importlib
import os
import queue
import re
import sys
import traceback
from importlib import util as importlib_util
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic, perf_counter, sleep, strftime

from client.client_logger import ClientLogger
from client.settings import dev_mode

REPO_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[3] / "scripts"
)  # repo/client/client/engine


USER_SCRIPTS_DIR = "~/.revenant/scripts"


def seed_scripts(target, bundled):
    """~/.revenant/scripts for a packaged build (#60): every bundled
    script copied in once; a script already there is the user's — maybe
    edited — and is never overwritten. Returns the directory."""
    target = Path(target).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    for source in sorted(Path(bundled).glob("*.py")):
        copy = target / source.name
        if not copy.exists():
            copy.write_bytes(source.read_bytes())
    return target


def default_scripts_dir():
    """Where scripts live: REVENANT_SCRIPTS, else ./scripts when the
    working directory has one, else the repo's own scripts/ — a session
    started from any other directory found no scripts at all and
    answered `;go2` with "no script named 'go2'" (captured 2026-09-04,
    #142). A packaged build has no repo: its bundled scripts seed
    ~/.revenant/scripts, which is then the directory (#60)."""
    if override := os.environ.get("REVENANT_SCRIPTS"):
        return Path(override)
    from client.engine.procspawn import bundle_dir

    bundle = bundle_dir()
    if bundle is not None:
        return seed_scripts(USER_SCRIPTS_DIR, bundle / "scripts")
    local = Path("scripts")
    if local.is_dir():
        return local
    return REPO_SCRIPTS_DIR


class ScriptStopped(Exception):
    """Raised inside a script's thread when it has been told to stop."""


class Script:
    """A running script's handle on the game — the `s` in main(s)."""

    def __init__(self, name, args, manager):
        self.name = name
        self.args = args
        self._manager = manager
        self._queue = queue.Queue(maxsize=1000)
        self._commands = queue.Queue(maxsize=100)
        self._stop = Event()
        # name -> {"patterns", "streams", "match"}: lines watched for while
        # the script does other things (#279, lich-5's Flags).
        self._flags = {}
        self._flags_lock = Lock()
        self.thread = None
        self.started_at = None  # wall clock, for the reload log line (#181)

    # -- API for script code --------------------------------------------

    def put(self, command: str, cleanup: bool = False):
        """Send a command to the game, echoing it to the front ends.

        After a ;stop every call raises ScriptStopped — except one with
        `cleanup=True`, which goes out anyway: for a finally: clause that
        puts an item back (;cast stopped between the GET and the stow
        left the cambrinth piece in hand, 2026-09-20). Nothing is read
        back; a cleanup put is fire-and-forget. One after the stop, while the
        character is stunned or in roundtime, is held by the manager and
        sent once they pass, in order (#318: a `;stop boxes` under a
        laughing-gas stun sent GET and WEAR blind, and the gauntlets
        stayed in the backpack)."""
        if not cleanup:
            self._check()
        self._manager.emit(f"[{self.name}]> {command}")
        self._manager.log.debug(f"[{self.name}]> {command}")
        state = self.state
        self._sent = (
            getattr(state, "prompt_count", None) if state is not None else None,
            self._manager.clock(),
        )
        if cleanup and self._stop.is_set():
            self._manager.send_cleanup(command, self.name)
        else:
            self._manager.send(command)

    def echo(self, text: str):
        """Show text in the front ends without sending anything to the game.

        The line goes into the session's debug log too (INFO, with the
        commands a script puts at DEBUG): a hunt's six "unrecognized ...
        answer" reports had scrolled off the window and nothing held
        them, so two could not be traced (2026-09-20, #241)."""
        self._manager.emit(f"[{self.name}] {text}")
        self._manager.log.info(f"[{self.name}] {text}")

    def emit(self, text: str, stream: str):
        """Show text in the front ends on a chosen stream — e.g. "thoughts"
        lands in the Thoughts dock. No script-name prefix is added."""
        self._check()
        self._manager.emit_stream(text, stream)

    def get(self, timeout=None, streams=("",)):
        """Return the next game line (main stream by default), or None on
        timeout. Pass streams=None to receive every stream as (stream, text).
        timeout=0 polls what is already queued without blocking."""
        deadline = None if timeout is None else self._manager.clock() + timeout
        while True:
            item = self._take(self._queue, deadline)
            if item is None:
                return None
            stream, text = item
            if streams is None:
                return stream, text
            if stream in streams:
                return text

    def command(self, timeout=None):
        """The next line a user handed to this running script — typing
        `;<name> <line>` while it runs delivers `<line>` here. None on
        timeout; timeout=0 polls without blocking."""
        deadline = None if timeout is None else self._manager.clock() + timeout
        return self._take(self._commands, deadline)

    def flag(self, name, *patterns, streams=("", "combat")):
        """Watch for a line matching any of the regex `patterns` on the
        story (and combat) stream while the script does other things
        (#279, after lich-5's Flags): the first matching line is kept
        under `name` until flagged() reads it. Re-flagging a name
        replaces its patterns and clears any match."""
        self._check()
        compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        with self._flags_lock:
            self._flags[name] = {
                "patterns": compiled,
                "streams": tuple(streams),
                "match": None,
            }

    def flagged(self, name, clear=True):
        """The line that matched flag `name` since it was set or last
        read, or None; `clear` (the default) forgets it so the next
        match is seen anew."""
        self._check()
        with self._flags_lock:
            entry = self._flags.get(name)
            if entry is None:
                return None
            line = entry["match"]
            if clear:
                entry["match"] = None
            return line

    def unflag(self, name):
        """Stop watching `name`."""
        with self._flags_lock:
            self._flags.pop(name, None)

    def _take(self, source, deadline):
        """The next item off a queue, or None once the deadline (manager
        clock; None = wait forever) passes. Wakes every quarter second
        to notice a stop, so a blocked script never outlives ;stop."""
        while True:
            self._check()
            try:
                return source.get_nowait()
            except queue.Empty:
                pass
            remaining = 0.25
            if deadline is not None:
                remaining = min(0.25, deadline - self._manager.clock())
                if remaining <= 0:
                    return None
            try:
                return source.get(timeout=remaining)
            except queue.Empty:
                continue

    def waitfor(self, *patterns, timeout=None, streams=("",)):
        """Block until a line matches any regex; return the line, or None
        on timeout."""
        compiled = [re.compile(pattern) for pattern in patterns]
        deadline = None if timeout is None else self._manager.clock() + timeout
        while True:
            remaining = None if deadline is None else deadline - self._manager.clock()
            if remaining is not None and remaining <= 0:
                return None
            line = self.get(timeout=remaining, streams=streams)
            if line is None:
                return None
            if any(pattern.search(line) for pattern in compiled):
                return line

    def sleep(self, seconds: float):
        """Sleep, but wake immediately (raising ScriptStopped) if stopped."""
        if self._stop.wait(timeout=seconds):
            raise ScriptStopped()

    def waitrt(self, pad=0.15, cast=False):
        """Sleep out any active roundtime — and, with `cast`, the spell
        pattern's formation time too.

        A forming pattern does not hold your commands, only the CAST: a
        plain waitrt after PREPARE used to sleep the cast time out as if
        it were a roundtime, so the swing meant to fill the formation
        went out only after "You feel fully prepared" — thirty seconds of
        badger bites with nothing sent, every training cast (#249,
        2026-09-20). Remaining time is the announced end (server clock)
        minus the last prompt's server time; if no fresher prompt arrives
        while sleeping, the local sleep is trusted and we return."""
        state = self.state
        if state is None or state.server_time is None:
            return
        # A waitrt straight after put() must see the command's own
        # answer first: the roundtime it opens arrives with the prompt
        # that closes it, a few hundred milliseconds later, and reading
        # the previous, spent roundtime meanwhile sent ;athletics' next
        # climb one second into a two-second roundtime ("...wait 1
        # seconds.", 2026-09-12). Wait for a prompt past the one seen at
        # the send, up to PROMPT_SETTLE seconds.
        sent = getattr(self, "_sent", None)
        if sent is not None and sent[0] is not None:
            count, at = sent
            while (
                getattr(state, "prompt_count", count) <= count
                and self._manager.clock() - at < PROMPT_SETTLE
            ):
                self.sleep(0.05)
            self._sent = None
        seen = state.server_time
        remaining = (
            max(state.roundtime, state.casttime) if cast else state.roundtime
        ) - seen
        while remaining > 0:
            self.sleep(remaining + pad)
            if state.server_time == seen:
                return
            seen = state.server_time
            remaining = (
                max(state.roundtime, state.casttime) if cast else state.roundtime
            ) - seen

    @property
    def dead(self):
        """True while the character is dead (the IconDEAD indicator).
        Movement and training scripts must check this: a corpse takes
        no commands, and only deathwatch may act on death (#91)."""
        state = self._manager.state
        indicators = getattr(state, "indicator", None) or {}
        return indicators.get("IconDEAD") == "y"

    @property
    def state(self):
        """The session's XMLData: indicators, prompt, server_time, ..."""
        return self._manager.state

    @property
    def status(self):
        """The state in words (client/game/status.py): s.status.stunned,
        .posture, .hands_empty, .roundtime, .mindstate("Athletics"),
        .summary() — a live view, derived on every access."""
        from client.game.status import status

        return status(self._manager.state)

    # -- other scripts: what an orchestrator (;train) needs -------------

    def run(self, name: str, args=()):
        """Start another script, as ;run <name> [args] would; True when
        it started. False — with the reason echoed the usual way — when
        there is no such script, it failed to load, or it is already
        running (a script the user started by hand is theirs)."""
        self._check()
        return self._manager.start(name, list(args))

    def is_running(self, name: str):
        """True while that script's thread is alive."""
        return self._manager.alive(name)

    def running_scripts(self):
        """The names of every script running now, this one included —
        ;sentinel tells an idle character from one a script is acting
        on by it (2026-09-26)."""
        return self._manager.names()

    def tell(self, name: str, line: str):
        """Hand a line to a running script, as typing ;<name> <line>
        would (it arrives through that script's s.command()). False
        when the script is not running."""
        script = self._manager.script(name)
        if script is None:
            return False
        script.feed_command(line)
        return True

    def kill(self, name: str):
        """Stop another script; nothing when it is not running. Safe to
        call while this script is itself being stopped, so a finally:
        clause can take a child down with its parent."""
        script = self._manager.script(name)
        if script is not None:
            script.stop()

    def crashed(self, name: str):
        """How that script's last run died — "ValueError(...) (file:line)"
        — or None when it exited cleanly, was stopped, or never ran.
        Cleared when the script starts again (#181)."""
        return self._manager.crashes.get(name)

    # -- plumbing --------------------------------------------------------

    def _check(self):
        if self._stop.is_set():
            raise ScriptStopped()

    def feed(self, text: str, stream: str):
        if self._flags:
            with self._flags_lock:
                for entry in self._flags.values():
                    if (
                        entry["match"] is None
                        and stream in entry["streams"]
                        and any(pattern.search(text) for pattern in entry["patterns"])
                    ):
                        entry["match"] = text
        try:
            self._queue.put_nowait((stream, text))
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait((stream, text))

    def feed_command(self, text: str):
        try:
            self._commands.put_nowait(text)
        except queue.Full:
            pass  # a script that never reads commands should not explode

    def stop(self):
        self._stop.set()

    @property
    def alive(self):
        return self.thread is not None and self.thread.is_alive()


# The client/ modules a script start reloads when their file changed
# since import (#138): pure logic, no cross-session state, in dependency
# order (walker binds names from mapdb, so mapdb reloads first). Never
# session, core, xml_data or this module — they own the socket, the
# parser and the threads, and only ;reexec may replace them.
# The convention every script keeps: a typed `;<name> return` is the
# graceful end. At a script that is not running it is nothing to do,
# never a launch with an argument the script ignores (#298).
RETURN_WORD = "return"

RELOADABLE_MODULES = (
    "client.settings",
    "client.ui.textfont",
    "client.game.eltime",
    "client.game.rested",
    "client.game.climbs",
    "client.game.circles",
    "client.game.inventory",
    "client.game.possessions",  # binds _depth from inventory: after it
    "client.game.probe",
    "client.game.loop",
    "client.game.creatures_data",
    "client.game.creatures",  # binds CAPS from creatures_data: after it
    "client.game.discard",
    "client.game.buffs",
    "client.game.profile",
    "client.game.training",  # binds names from profile: after it
    "client.game.drain",
    "client.game.tdp",
    "client.game.money",
    "client.game.bank",  # binds names from money and soul: after them
    "client.game.attune",
    "client.game.seek",  # binds chain/circuit from attune: after it
    "client.game.perform",
    "client.game.appraisal",
    "client.game.research",
    "client.game.repair",
    "client.game.remedies",
    "client.game.workorders",  # binds the catalogs from remedies: after it
    "client.game.justice",
    "client.game.teaching",
    "client.game.helper",
    "client.game.loot",  # binds noun_of from creatures: after it
    "client.game.boxes",  # binds BOX_NOUNS from loot: after it
    "client.game.lootlog",  # binds BOX_NOUNS from loot: after it
    "client.game.scholarship",
    "client.game.soul",
    "client.game.encumbrance",
    "client.game.status",
    "client.game.novelty",
    "client.game.flight",  # binds status: after it
    "client.game.mapdb",
    "client.game.walker",
    "client.game.climblog",  # binds the refusals from walker: after it
    "client.game.wounds_data",
    "client.game.wounds",  # binds ROWS from wounds_data: after it
    "client.game.empathy",  # binds level from wounds: after it
    "client.game.herbs_data",
    "client.game.herbs",  # binds HERBS/SHOPS from herbs_data: after it
)


# A stopped script's cleanup puts wait out a stun or roundtime this
# long at most, looked at this often, then go out anyway (#318).
CLEANUP_HOLD_SECONDS = 300
CLEANUP_POLL = 0.5

# A script start that takes this long to load — helper reloads and the
# script's own imports — is reported in developer mode (settings
# dev_mode / REVENANT_DEV=1). Loads are normally milliseconds; a slow one
# means an import doing work it should defer (networkx, a map read).
SLOW_LOAD_SECONDS = 0.5
# How long waitrt() straight after put() waits for the command's own
# prompt before trusting the roundtime it reads (an answer's prompt
# lands within a few hundred milliseconds; a lagging one gets this).
PROMPT_SETTLE = 1.5


def _mtime(module):
    path = getattr(module, "__file__", None)
    try:
        return os.path.getmtime(path) if path else None
    except OSError:
        return None


def _fresh_import(name):
    """Import `name` as a new module object, leaving the old one to
    whoever still holds it. On failure the old module is back in
    sys.modules and on its package, and the error propagates."""
    old = sys.modules.pop(name)
    try:
        return importlib.import_module(name)
    except BaseException:
        sys.modules[name] = old
        parent, _, child = name.rpartition(".")
        if parent and parent in sys.modules:
            setattr(sys.modules[parent], child, old)
        raise


class ScriptManager(ClientLogger):
    """Loads, runs, feeds, and stops scripts inside the session."""

    def __init__(
        self,
        send,
        emit,
        state=None,
        scripts_dir=None,
        clock=None,
        emit_stream=None,
        reloadable=RELOADABLE_MODULES,
    ):
        self.send = send  # (str) -> None: command to the game
        self.emit = emit  # (str) -> None: text to the front ends
        # (str, str) -> None: text to the front ends on a chosen stream;
        # without one, the stream is dropped and text goes the plain way.
        self.emit_stream = emit_stream or (lambda text, stream: self.emit(text))
        self.state = state
        self.scripts_dir = Path(scripts_dir) if scripts_dir else default_scripts_dir()
        # Injectable for tests; scripts see time through their manager.
        self.clock = clock or monotonic
        self.running = {}
        self.crashes = {}  # name -> how its last run died (#181)
        self.lock = Lock()
        # File stamps of the reloadable modules as last imported/reloaded;
        # a module is stamped when first seen imported (#138).
        self.reloadable = tuple(reloadable)
        self._module_stamps = {}
        self._moved_warned = False  # the "restart the session" line, once (#155)
        # Stopped scripts' cleanup puts held for a stun or roundtime (#318).
        self._held = []
        self._held_lock = Lock()
        self._held_thread = None
        self._stamp_modules()

    # -- cleanup puts held for a stun (#318) ------------------------------

    def _blocked(self):
        """True while the character cannot act on a command: stunned, or
        in roundtime by the game's clock."""
        if self.state is None:
            return False
        from client.game.status import status

        now = status(self.state)
        return bool(now.stunned or now.roundtime)

    def send_cleanup(self, command, name=""):
        """A stopped script's cleanup put: sent now when the character can
        act and nothing is held before it, else held — the first one
        said — and sent by a worker once the stun and roundtime pass, or
        after CLEANUP_HOLD_SECONDS whatever they say."""
        with self._held_lock:
            if not self._held and not self._blocked():
                self.send(command)
                return
            if not self._held:
                self.emit(
                    f"[{name}] holding the cleanup until the stun or roundtime passes"
                )
            self._held.append(command)
            if self._held_thread is None or not self._held_thread.is_alive():
                self._held_thread = Thread(
                    target=self._send_held, name="cleanup-held", daemon=True
                )
                self._held_thread.start()

    def _send_held(self):
        deadline = self.clock() + CLEANUP_HOLD_SECONDS
        while True:
            sleep(CLEANUP_POLL)
            with self._held_lock:
                if not self._held:
                    return
                if self._blocked() and self.clock() < deadline:
                    continue
                # One per look: the next waits out any roundtime this
                # one brings (a GET, then the WEAR).
                self.send(self._held.pop(0))

    # -- helper-module reload (#138) ------------------------------------

    def _stamp_modules(self):
        for name in self.reloadable:
            module = sys.modules.get(name)
            if module is not None and name not in self._module_stamps:
                self._module_stamps[name] = _mtime(module)

    def reload_changed(self):
        """Reload the reloadable modules whose file changed since they
        were imported; returns the names that had changed.

        One change reloads every imported reloadable module, in list
        order: a module that binds names from an earlier one (walker
        from mapdb) must re-import them from the fresh copy, and a
        blanket reload in dependency order needs no import graph. Each
        reload is a fresh module object (#181): the scripts already
        running keep the functions they imported and those functions
        keep the globals they were written against, so an edit that
        changes a helper's signature cannot reach into a running walk.
        A reload that fails (a syntax error mid-edit) is reported and
        the module keeps running its last good code."""
        changed = [
            name
            for name, stamp in self._module_stamps.items()
            if _mtime(sys.modules[name]) != stamp
        ]
        if not changed:
            return []
        with self.lock:
            keepers = [
                f"{script.name} (started {script.started_at})"
                for script in self.running.values()
                if script.alive
            ]
        if keepers:
            self.log.info(
                f"reloading {', '.join(changed)} as fresh copies; running scripts "
                f"keep the code they imported: {', '.join(keepers)}"
            )
        moved = []
        for name in self.reloadable:
            module = sys.modules.get(name)
            if module is None:
                continue
            try:
                _fresh_import(name)
            except ModuleNotFoundError:
                # The file is gone from where it was imported — the
                # module moved (a regroup like 63c98c7). One line for
                # all of them, once, saying what helps (#155).
                moved.append(name)
                continue
            except Exception as error:
                self.log.exception(f"failed to reload {name}")
                self.emit(f"{name} failed to reload, keeping the old code: {error!r}")
                continue
            self._module_stamps[name] = _mtime(sys.modules[name])
        if moved and not self._moved_warned:
            self._moved_warned = True
            self.log.warning(f"helper modules moved since import: {', '.join(moved)}")
            self.emit(
                "the helper modules moved since this session started "
                f"({', '.join(moved)}) — the old code keeps running; restart "
                "the session (quit the window and relaunch) to pick up the new"
            )
        return changed

    # -- game-line fan-in ------------------------------------------------

    def feed(self, text: str, stream: str):
        with self.lock:
            scripts = list(self.running.values())
        for script in scripts:
            script.feed(text, stream)

    # -- ;-command handling ---------------------------------------------

    # lich muscle memory: these top-level ;-commands belong to the lnet
    # script (lich intercepts ;chat/;reply/... and hands them to lnet).
    LNET_SHORTHANDS = ("chat", "reply", "who", "stats", "channels", "tune", "untune")

    def handle_command(self, line: str):
        """Handle a `;...` line typed in a front end."""
        body = line.lstrip(";").strip()
        if not body:
            self.emit(
                "script commands: ;list  ;help [name]  ;<name> help  "
                ";run <name> [args]  ;stop <name|all>"
            )
            return
        command, _, rest = body.partition(" ")
        rest = rest.strip()
        if command == "list":
            self.list_scripts()
        elif command == "help":
            self.help(rest or None)
        elif command in ("stop", "k", "kill"):  # ;k / ;kill: lich muscle memory
            self.stop(rest or "all")
        elif command == "run":
            if not rest:
                self.emit("usage: ;run <name> [args]")
            else:
                args = rest.split()
                self.start(args[0], args[1:])
        elif command in self.LNET_SHORTHANDS:
            self.deliver("lnet", f"{command} {rest}".strip(), queue_on_start=True)
        else:
            self.deliver(command, rest)

    def deliver(self, name: str, payload: str, queue_on_start=False):
        """Hand a line to a running script; start the script when it isn't.

        `;<name> help` is answered here for every script, running or
        not: its docstring, the same page ;help <name> shows, and the
        script is neither started nor handed the word. Otherwise
        `;<name> <line>` reaches a running script through s.command().
        A bare `;<name>` on a running script is refused like before. With
        queue_on_start (the lnet shorthands), a stopped script is started
        and the line queued for it — `;chat hi` works from cold."""
        if payload.split()[:1] == ["help"]:
            self.help(name)
            return
        with self.lock:
            script = self.running.get(name)
        if script is not None and script.alive:
            if payload:
                script.feed_command(payload)
            else:
                self.emit(f"{name} is already running (;stop {name} first)")
            return
        if payload.split() == [RETURN_WORD]:
            # The graceful-end word at a script that is not running is
            # not a launch (#298: `;remedies return` twenty seconds after
            # `;stop train` had taken the task down started a training
            # run, and its leftover salve broke the next order).
            self.emit(f"{name} is not running — nothing to return from")
            return
        self.start(name, [] if queue_on_start else payload.split())
        if queue_on_start and payload:
            with self.lock:
                script = self.running.get(name)
            if script is not None:
                script.feed_command(payload)

    def available(self):
        if not self.scripts_dir.is_dir():
            return []
        return sorted(path.stem for path in self.scripts_dir.glob("*.py"))

    def script_doc(self, name: str):
        """A script's module docstring, read without executing the file.
        None when the script (or a parseable docstring) doesn't exist."""
        path = self.scripts_dir / f"{name}.py"
        if not path.is_file():
            return None
        try:
            return ast.get_docstring(ast.parse(path.read_text()))
        except (OSError, SyntaxError):
            return None

    def help(self, name=None):
        """;help — one line per script; ;help <name> — the full docstring."""
        if name is None:
            available = self.available()
            if not available:
                self.emit(f"no scripts in {self.scripts_dir}/")
                return
            for script_name in available:
                doc = self.script_doc(script_name) or ""
                summary = doc.strip().splitlines()[0] if doc.strip() else "(no help)"
                self.emit(f"{script_name} — {summary}")
            return
        if not (self.scripts_dir / f"{name}.py").is_file():
            self.emit(f"no script named {name!r} in {self.scripts_dir}/ (try ;list)")
            return
        doc = self.script_doc(name)
        self.emit(doc.strip() if doc else f"{name} has no docstring to show")

    def list_scripts(self):
        with self.lock:
            running = sorted(self.running)
        self.emit(f"running: {', '.join(running) or '(none)'}")
        self.emit(
            f"available in {self.scripts_dir}/: {', '.join(self.available()) or '(none)'}"
        )

    def script(self, name: str):
        """The running script of that exact name, or None."""
        with self.lock:
            script = self.running.get(name)
        return script if script is not None and script.alive else None

    def alive(self, name: str):
        return self.script(name) is not None

    def names(self):
        """The names of the scripts running now, sorted."""
        with self.lock:
            scripts = list(self.running.values())
        return sorted(script.name for script in scripts if script.alive)

    def start(self, name: str, args):
        """Start a script; True when its thread is running. False — the
        reason emitted — when there is no such script, it failed to
        load, or it is already running."""
        path = self.scripts_dir / f"{name}.py"
        if not path.is_file():
            self.emit(f"no script named {name!r} in {self.scripts_dir}/ (try ;list)")
            return False
        with self.lock:
            if name in self.running and self.running[name].alive:
                self.emit(f"{name} is already running (;stop {name} first)")
                return False
        started = perf_counter()
        changed = self.reload_changed()
        if changed:
            with self.lock:
                keepers = [s.name for s in self.running.values() if s.alive]
            keeping = (
                f"; {', '.join(keepers)} keeps the code it started with"
                if keepers
                else ""
            )
            self.emit(f"reloaded {', '.join(changed)} (edited since import){keeping}")
        try:
            spec = importlib_util.spec_from_file_location(
                f"revenant_script_{name}", path
            )
            module = importlib_util.module_from_spec(spec)
            spec.loader.exec_module(module)
            entry = module.main
        except Exception as error:
            self.log.exception(f"failed to load script {name}")
            self.emit(f"{name} failed to load: {error!r}")
            return False
        # A script's first import of a helper is stamped here, so a
        # later edit to it is noticed at the next start.
        self._stamp_modules()
        self._report_slow_load(name, perf_counter() - started, changed)
        script = Script(name, args, self)
        script.started_at = strftime("%H:%M:%S")
        script.thread = Thread(target=self._run, args=(script, entry), daemon=True)
        with self.lock:
            self.running[name] = script
            self.crashes.pop(name, None)
        script.thread.start()
        return True

    def _report_slow_load(self, name, seconds, changed):
        """Developer mode only: a load past SLOW_LOAD_SECONDS is worth a
        line — with what reloaded, since reloads are the usual cause."""
        self.log.debug(f"{name} loaded in {seconds:.3f}s (reloaded: {changed})")
        if seconds < SLOW_LOAD_SECONDS or not dev_mode():
            return
        detail = f" (reloaded {', '.join(changed)})" if changed else ""
        self.emit(f"{name} took {seconds:.1f}s to load{detail}")

    def _run(self, script, entry):
        self.emit(f"{script.name} started")
        try:
            entry(script)
        except ScriptStopped:
            self.emit(f"{script.name} stopped")
        except Exception as error:
            self.log.exception(f"script {script.name} crashed")
            last_frame = traceback.extract_tb(error.__traceback__)[-1]
            where = f"{error!r} ({last_frame.filename}:{last_frame.lineno})"
            with self.lock:
                self.crashes[script.name] = where
            self.emit(f"{script.name} crashed: {where}")
        else:
            self.emit(f"{script.name} exited")
        finally:
            with self.lock:
                if self.running.get(script.name) is script:
                    del self.running[script.name]

    # ;stop all leaves the background monitors running — the scripts
    # the session autostarts (the death watch, the exp and wealth
    # logs, the sheet, the dashboard, the chat): an emergency stop
    # during the invasion of 2026-09-22 took ;deathwatch down with the
    # trainers and it had to be restarted by hand (#285; the operator:
    # "shouldn't stop background monitoring scripts like ;xp or
    # ;deathwatch"). ;stop <name> stops one of them on its own.
    KEEP_ON_STOP_ALL = ("deathwatch", "xp", "wealth", "sheet", "beholder", "lnet")

    def stop(self, name: str):
        with self.lock:
            if name == "all":
                targets = [
                    script
                    for script in self.running.values()
                    if script.name not in self.KEEP_ON_STOP_ALL
                ]
                kept = [
                    script.name
                    for script in self.running.values()
                    if script.name in self.KEEP_ON_STOP_ALL
                ]
            elif name in self.running:
                targets = [self.running[name]]
            else:
                # ;k mech — a prefix is enough when it names one script
                targets = [
                    script
                    for running_name, script in self.running.items()
                    if running_name.startswith(name)
                ]
        if name != "all" and len(targets) > 1:
            names = ", ".join(sorted(script.name for script in targets))
            self.emit(f"{name!r} matches several running scripts: {names}")
            return
        if name == "all" and kept:
            self.emit(
                f"kept running: {', '.join(sorted(kept))} — the background "
                f"monitors; ;stop {sorted(kept)[0]} stops one"
            )
        if not targets:
            self.emit(f"nothing to stop ({name})")
            return
        for script in targets:
            script.stop()

    def stop_all(self):
        """Internal shutdown path: stop everything without the ;stop
        feedback chatter (an empty "nothing to stop" has no audience)."""
        with self.lock:
            targets = list(self.running.values())
        for script in targets:
            script.stop()
