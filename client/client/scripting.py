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
walker, mapdb, inventory, ...) when their files changed since they were
imported — so a fix in the walker reaches a running session through
;stop go2 and ;go2, the way lich's common scripts do (#138). Modules
holding the socket, the parser, or threads never reload; that is
;reexec's job.
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
from time import monotonic

from client.client_logger import ClientLogger

DEFAULT_SCRIPTS_DIR = os.environ.get("REVENANT_SCRIPTS", "scripts")


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
        self.thread = None

    # -- API for script code --------------------------------------------

    def put(self, command: str):
        """Send a command to the game, echoing it to the front ends."""
        self._check()
        self._manager.emit(f"[{self.name}]> {command}")
        self._manager.send(command)

    def echo(self, text: str):
        """Show text in the front ends without sending anything to the game."""
        self._manager.emit(f"[{self.name}] {text}")

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

    def waitrt(self, pad=0.15):
        """Sleep out any active roundtime or spellcast time.

        Remaining time is the announced end (server clock) minus the last
        prompt's server time; if no fresher prompt arrives while sleeping,
        the local sleep is trusted and we return."""
        state = self.state
        if state is None or state.server_time is None:
            return
        seen = state.server_time
        remaining = max(state.roundtime, state.casttime) - seen
        while remaining > 0:
            self.sleep(remaining + pad)
            if state.server_time == seen:
                return
            seen = state.server_time
            remaining = max(state.roundtime, state.casttime) - seen

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

    # -- plumbing --------------------------------------------------------

    def _check(self):
        if self._stop.is_set():
            raise ScriptStopped()

    def feed(self, text: str, stream: str):
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
RELOADABLE_MODULES = (
    "client.settings",
    "client.textfont",
    "client.eltime",
    "client.climbs",
    "client.circles",
    "client.inventory",
    "client.probe",
    "client.mapdb",
    "client.walker",
)


def _mtime(module):
    path = getattr(module, "__file__", None)
    try:
        return os.path.getmtime(path) if path else None
    except OSError:
        return None


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
        self.scripts_dir = Path(scripts_dir or DEFAULT_SCRIPTS_DIR)
        # Injectable for tests; scripts see time through their manager.
        self.clock = clock or monotonic
        self.running = {}
        self.lock = Lock()
        # File stamps of the reloadable modules as last imported/reloaded;
        # a module is stamped when first seen imported (#138).
        self.reloadable = tuple(reloadable)
        self._module_stamps = {}
        self._stamp_modules()

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
        blanket reload in dependency order needs no import graph. A
        reload that fails (a syntax error mid-edit) is reported and the
        module keeps running its last good code."""
        changed = [
            name
            for name, stamp in self._module_stamps.items()
            if _mtime(sys.modules[name]) != stamp
        ]
        if not changed:
            return []
        for name in self.reloadable:
            module = sys.modules.get(name)
            if module is None:
                continue
            try:
                importlib.reload(module)
            except Exception as error:
                self.log.exception(f"failed to reload {name}")
                self.emit(f"{name} failed to reload, keeping the old code: {error!r}")
                continue
            self._module_stamps[name] = _mtime(sys.modules[name])
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
                "script commands: ;list  ;help [name]  ;run <name> [args]  "
                ";stop <name|all>"
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

        `;<name> <line>` reaches a running script through s.command().
        A bare `;<name>` on a running script is refused like before. With
        queue_on_start (the lnet shorthands), a stopped script is started
        and the line queued for it — `;chat hi` works from cold."""
        with self.lock:
            script = self.running.get(name)
        if script is not None and script.alive:
            if payload:
                script.feed_command(payload)
            else:
                self.emit(f"{name} is already running (;stop {name} first)")
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

    def start(self, name: str, args):
        path = self.scripts_dir / f"{name}.py"
        if not path.is_file():
            self.emit(f"no script named {name!r} in {self.scripts_dir}/ (try ;list)")
            return
        with self.lock:
            if name in self.running and self.running[name].alive:
                self.emit(f"{name} is already running (;stop {name} first)")
                return
        changed = self.reload_changed()
        if changed:
            self.emit(f"reloaded {', '.join(changed)} (edited since import)")
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
            return
        # A script's first import of a helper is stamped here, so a
        # later edit to it is noticed at the next start.
        self._stamp_modules()
        script = Script(name, args, self)
        script.thread = Thread(target=self._run, args=(script, entry), daemon=True)
        with self.lock:
            self.running[name] = script
        script.thread.start()

    def _run(self, script, entry):
        self.emit(f"{script.name} started")
        try:
            entry(script)
        except ScriptStopped:
            self.emit(f"{script.name} stopped")
        except Exception as error:
            self.log.exception(f"script {script.name} crashed")
            last_frame = traceback.extract_tb(error.__traceback__)[-1]
            self.emit(
                f"{script.name} crashed: {error!r} "
                f"({last_frame.filename}:{last_frame.lineno})"
            )
        else:
            self.emit(f"{script.name} exited")
        finally:
            with self.lock:
                if self.running.get(script.name) is script:
                    del self.running[script.name]

    def stop(self, name: str):
        with self.lock:
            if name == "all":
                targets = list(self.running.values())
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
