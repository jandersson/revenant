"""The script engine: player-written Python running inside the session.

A script is a .py file in the scripts directory defining `main(s)`. It runs
in its own thread with `s` as its handle on the game:

    s.put("look")                      # send a command (echoed to front ends)
    line = s.get(timeout=5)            # next main-stream line, None on timeout
    line = s.waitfor(r"Obvious paths", timeout=10)
    s.echo("done!")                    # front-end-only output
    s.emit("psst", "thoughts")         # front-end output on a chosen stream
    s.sleep(2)                         # stop-aware sleep
    s.state                            # the session's XMLData (indicators etc.)
    s.args                             # arguments from `;run name arg1 arg2`

Scripts are controlled from any attached front end with ;-commands:
;list, ;run <name> [args], ;stop <name|all>, or ;<name> [args] as shorthand.
"""

import os
import queue
import re
import traceback
from importlib import util as importlib_util
from pathlib import Path
from threading import Event, Lock, Thread

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
        timeout. Pass streams=None to receive every stream as (stream, text)."""
        deadline = None if timeout is None else self._manager.clock() + timeout
        while True:
            self._check()
            remaining = 0.25
            if deadline is not None:
                remaining = min(0.25, deadline - self._manager.clock())
                if remaining <= 0:
                    return None
            try:
                stream, text = self._queue.get(timeout=remaining)
            except queue.Empty:
                continue
            if streams is None:
                return stream, text
            if stream in streams:
                return text

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

    def stop(self):
        self._stop.set()

    @property
    def alive(self):
        return self.thread is not None and self.thread.is_alive()


class ScriptManager(ClientLogger):
    """Loads, runs, feeds, and stops scripts inside the session."""

    def __init__(
        self, send, emit, state=None, scripts_dir=None, clock=None, emit_stream=None
    ):
        self.send = send  # (str) -> None: command to the game
        self.emit = emit  # (str) -> None: text to the front ends
        # (str, str) -> None: text to the front ends on a chosen stream;
        # without one, the stream is dropped and text goes the plain way.
        self.emit_stream = emit_stream or (lambda text, stream: self.emit(text))
        self.state = state
        self.scripts_dir = Path(scripts_dir or DEFAULT_SCRIPTS_DIR)
        # Injectable for tests; scripts see time through their manager.
        from time import monotonic

        self.clock = clock or monotonic
        self.running = {}
        self.lock = Lock()

    # -- game-line fan-in ------------------------------------------------

    def feed(self, text: str, stream: str):
        with self.lock:
            scripts = list(self.running.values())
        for script in scripts:
            script.feed(text, stream)

    # -- ;-command handling ---------------------------------------------

    def handle_command(self, line: str):
        """Handle a `;...` line typed in a front end."""
        parts = line.lstrip(";").split()
        if not parts:
            self.emit("script commands: ;list  ;run <name> [args]  ;stop <name|all>")
            return
        command, args = parts[0], parts[1:]
        if command == "list":
            self.list_scripts()
        elif command == "stop":
            self.stop(args[0] if args else "all")
        elif command == "run":
            if not args:
                self.emit("usage: ;run <name> [args]")
            else:
                self.start(args[0], args[1:])
        else:
            self.start(command, args)

    def available(self):
        if not self.scripts_dir.is_dir():
            return []
        return sorted(path.stem for path in self.scripts_dir.glob("*.py"))

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
            else:
                targets = [self.running[name]] if name in self.running else []
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
