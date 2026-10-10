"""Drive a session from outside with a log, a stop file and a rate cap:
    uv run python tools/drive.py --character NAME [--act] [--answer N] "command"
    uv run python tools/drive.py --character NAME [--act] --steps FILE
    uv run python tools/drive.py --stop            # every driver halts before its next send
    uv run python tools/drive.py --go              # lift the stop

Every send and its answer is appended to ~/.revenant/logs/drive-<Name>-<stamp>.log
(REVENANT_LOG_DIR moves it) and printed unbuffered, so a loop run in the
background can be read at any moment. The stop file (~/.revenant/drive.stop)
is checked before each send; SENDS_PER_MINUTE caps the pace. A steps file
holds one command a line; `sleep N` waits, `# ...` is a comment. Sends go
through `revenant-send --origin claude`; --act opens the gate
(REVENANT_ALLOW_SEND=1) for commands that act, as the drive skill says.

Why: on 2026-10-10 a background shell loop drove a character with its
output behind a buffering pipe and a bug in it sent a bad command for ten
minutes unseen. The drive skill (.claude/skills/drive) is the procedure.
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SENDS_PER_MINUTE = 20
STOP_FILE = Path(
    os.environ.get("REVENANT_DRIVE_STOP") or Path.home() / ".revenant" / "drive.stop"
)


def log_dir():
    return Path(
        os.environ.get("REVENANT_LOG_DIR") or Path.home() / ".revenant" / "logs"
    )


class Driver:
    """Sends through revenant-send, each one logged, paced and stoppable."""

    def __init__(
        self,
        character,
        act=False,
        answer=4,
        sender=None,
        clock=time.monotonic,
        sleep=time.sleep,
        log=None,
    ):
        self.character = character
        self.act = act
        self.answer = answer
        self.sender = sender or self._send_for_real
        self.clock = clock
        self.sleep = sleep
        self.sent_at = []
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log = (
            log if log is not None else log_dir() / f"drive-{character}-{stamp}.log"
        )

    def _send_for_real(self, command):
        env = dict(os.environ)
        if self.act:
            env["REVENANT_ALLOW_SEND"] = "1"
        run = subprocess.run(
            [
                "uv",
                "run",
                "revenant-send",
                "--origin",
                "claude",
                "--answer",
                str(self.answer),
                "--character",
                self.character,
                command,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        return (run.stdout or "") + (run.stderr or "")

    def _note(self, text):
        line = f"{datetime.now().strftime('%H:%M:%S')} {text}"
        print(line, flush=True)
        if self.log:
            Path(self.log).parent.mkdir(parents=True, exist_ok=True)
            with open(self.log, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def stopped(self):
        return STOP_FILE.exists()

    def pace(self):
        """Wait until another send keeps under SENDS_PER_MINUTE."""
        now = self.clock()
        self.sent_at = [t for t in self.sent_at if now - t < 60]
        if len(self.sent_at) >= SENDS_PER_MINUTE:
            wait = 60 - (now - self.sent_at[0])
            self._note(
                f"pace: {SENDS_PER_MINUTE} sends in the last minute — waiting {wait:.0f} s"
            )
            self.sleep(max(0.0, wait))
        self.sent_at.append(self.clock())

    def send(self, command):
        """The command sent and its answer returned; None, said, when the
        stop file stands."""
        if self.stopped():
            self._note(f"STOP file {STOP_FILE} — not sending {command!r}")
            return None
        self.pace()
        self._note(f">> {command}")
        answer = self.sender(command)
        for line in (answer or "").splitlines():
            if line.strip():
                self._note(f"   {line.rstrip()}")
        return answer

    def run_steps(self, lines):
        """One command a line; `sleep N` waits; a blank or `#` line is skipped.
        False when the stop file ended it."""
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("sleep "):
                self.sleep(float(line.split()[1]))
                continue
            if self.send(line) is None:
                return False
        return True


def main(argv=None):
    # The console's code page is not UTF-8 on Windows: a script's echo with a
    # dash or the parser's replacement character crashed the print after the
    # send had gone out (2026-10-10). Print what can be printed.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", nargs="?", help="one command to send")
    parser.add_argument("--character")
    parser.add_argument(
        "--act", action="store_true", help="open the gate for a command that acts"
    )
    parser.add_argument(
        "--answer", type=int, default=4, help="seconds to read the answer"
    )
    parser.add_argument("--steps", help="a file of commands, one a line")
    parser.add_argument("--stop", action="store_true", help="raise the stop file")
    parser.add_argument("--go", action="store_true", help="lift the stop file")
    args = parser.parse_args(argv)
    if args.stop:
        STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
        STOP_FILE.touch()
        print(f"stop file raised: {STOP_FILE}")
        return 0
    if args.go:
        STOP_FILE.unlink(missing_ok=True)
        print("stop file lifted")
        return 0
    if not args.character or not (args.command or args.steps):
        parser.error("--character and a command or --steps are needed")
    driver = Driver(args.character, act=args.act, answer=args.answer)
    print(f"log: {driver.log}", flush=True)
    if args.steps:
        lines = Path(args.steps).read_text(encoding="utf-8").splitlines()
        return 0 if driver.run_steps(lines) else 3
    return 0 if driver.send(args.command) is not None else 3


if __name__ == "__main__":
    sys.exit(main())
