"""Send one command into a running session from outside:  revenant-send

    revenant-send [--character NAME] [--origin WHO] [--answer SECONDS] [--dry-run] <command words ...>
    revenant-send --state [FIELDS] [--character NAME]
    revenant-send --wait-for TEXT [--timeout SECONDS] [<command words ...>]

The supported, audited way for a tool or an agent to act on what it
worked out - ";go2 bank", "exp all", ";stop hunt" - instead of handing
the line over to be retyped (#135). It resolves the character's session
through the registry the launcher keeps, sends the line tagged with its
origin, and the session echoes it to every attached window as
">> [external] <command>" and logs it, so a command that was not typed
by the player never acts invisibly.

Off by default, in two tiers. Read-only commands on the allowlist
(INFO, EXP, SPELL, HEALTH, WEALTH, LOOK, TIME, INVENTORY, GLANCE, ASSESS,
TDP, ENCUMBRANCE, the eight stat words, PREMIUM, and the ;list / ;help /
;stop / ;sheet / ;clock scripts) go through whenever a session is
listening. Anything else - everything that spends, drops,
moves or attacks - needs the gate open: the "allow external sends"
setting (~/.revenant/settings.json, allow_external_send) or
REVENANT_ALLOW_SEND=1 for one call. --dry-run says what would happen
and sends nothing. --answer N stays attached for N seconds after the
send and prints what the game answered (the story lines that followed
the line's own echo, and the scripts' echoes — the "script" stream,
"[soul] ..." — when the line started one), so a tool reads the reply
here instead of tailing the log; --origin names the sender in that
echo (Claude sends as claude). Exit status 0 when the line went out (or a dry run), 1
when it was refused or nothing was listening.

Two read-only forms (#216) type nothing at the game and echo nothing
to a window. --state prints the parser's state as JSON — the room,
the vitals, the exp window, the hands, the status words, the
injuries, the spells, the room's players, creatures and objects, the
rested footer, the possessions (client/engine/snapshot.py) — all of
it, or the comma list given (`--state room,vitals`): what the docks
already show, so a driver reads it here instead of sending LOOK, EXP
or HEALTH at the character. --wait-for TEXT stays attached until a
story line holds TEXT or --timeout seconds pass (30 by default),
printing the story meanwhile, and exits 0 when the line came, 1 when
it did not; with a command it sends that first and then waits. Both
are allowlisted whatever the gate says.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass

from client.engine.registry import running_sessions
from client.engine.wire import DEFAULT_HOST, request_state, send_and_read, send_line
from client.settings import load_settings

# A line the session reads as "sent from outside": \x1e<origin>\t<command>.
EXTERNAL_MARK = "\x1e"
DEFAULT_ORIGIN = "external"

# Game commands that only ask: first word, lower-case.
ALLOWLIST = frozenset(
    {
        "info",
        "exp",
        "experience",
        "spell",
        "spells",
        "health",
        "wealth",
        "look",
        "time",
        "inventory",
        "inv",
        "glance",
        "assess",
        # the stat quotes, the TDP figures, the burden and the account
        # perks: answers, no roundtime, nothing changed (2026-09-12)
        "tdp",
        "encumbrance",
        "enc",
        "strength",
        "reflex",
        "agility",
        "charisma",
        "discipline",
        "wisdom",
        "intelligence",
        "stamina",
        "premium",
    }
)
# Scripts that only read or stop something.
SCRIPT_ALLOWLIST = frozenset({";list", ";help", ";stop", ";sheet", ";clock"})


@dataclass
class Result:
    sent: bool
    message: str
    host: str = DEFAULT_HOST
    port: int | None = None
    command: str = ""
    answer: str = ""
    found: bool | None = None  # --wait-for: the line came (None: no wait)
    state: dict | None = None  # --state: the session's answer

    @property
    def ok(self):
        """Exit-status sense: the line went out (or a dry run said its
        piece), and a waited-for line came."""
        went = self.sent or self.message.startswith("dry run")
        return went and self.found is not False


def allowlisted(command):
    """Whether a command is read-only enough to pass with the gate shut."""
    words = command.strip().split()
    if not words:
        return False
    first = words[0].lower()
    if first.startswith(";"):
        return first in SCRIPT_ALLOWLIST
    return first in ALLOWLIST


def gate_open(settings=None, environ=None):
    """The setting or the one-call environment override."""
    environ = os.environ if environ is None else environ
    if environ.get("REVENANT_ALLOW_SEND") == "1":
        return True
    settings = load_settings() if settings is None else settings
    return bool(settings.get("allow_external_send"))


def resolve_port(character=None, sessions=None, host=DEFAULT_HOST):
    """(port, message): the session playing `character`, or the only
    session when none is named. The message explains a None."""
    sessions = running_sessions(host) if sessions is None else list(sessions)
    if not sessions:
        return None, (
            "no session in the registry - if one is running, name its port with "
            "--port (a row can go missing for up to half a minute, #160)"
        )
    if character:
        wanted = character.strip().lower()
        for entry in sessions:
            if str(entry.get("character") or "").lower() == wanted:
                return int(entry["port"]), f"session for {entry['character']}"
        names = ", ".join(
            str(e.get("character") or f"port {e.get('port')}") for e in sessions
        )
        return None, (
            f"no session is playing {character!r} (running: {names}) - "
            "--port sends to one the registry has not listed yet"
        )
    if len(sessions) == 1:
        entry = sessions[0]
        return int(
            entry["port"]
        ), f"session for {entry.get('character') or 'an unnamed character'}"
    names = ", ".join(
        str(e.get("character") or f"port {e.get('port')}") for e in sessions
    )
    return None, f"several sessions are running ({names}) - name one with --character"


def _story(frames):
    return "".join(text for text, stream, _ in frames if stream == "")


def query_state(
    character=None,
    host=DEFAULT_HOST,
    port=None,
    fields=(),
    origin=DEFAULT_ORIGIN,
    sessions=None,
):
    """The session's parsed state in Result.state (#216), or why not.
    Read-only: no gate, nothing sent to the game, nothing echoed."""
    if port is None:
        port, why = resolve_port(character, sessions, host)
        if port is None:
            return Result(False, why, host, None)
    state = request_state(host, port, fields, origin)
    if state is None:
        return Result(False, f"no state answer from {host}:{port}", host, port)
    return Result(True, f"state from {host}:{port}", host, port, state=state)


def wait(
    text,
    character=None,
    host=DEFAULT_HOST,
    port=None,
    timeout=30.0,
    sessions=None,
):
    """Stay attached until a story line holds `text` or `timeout`
    seconds pass (#216): the story seen is Result.answer, Result.found
    says whether the line came. Nothing is sent."""
    if port is None:
        port, why = resolve_port(character, sessions, host)
        if port is None:
            return Result(False, why, host, None)
    frames = send_and_read(host, port, None, timeout, until=text)
    if frames is None:
        return Result(False, f"nothing is listening on {host}:{port}", host, port)
    found = any(text in line for line, stream, _ in frames if stream == "")
    seen = "came" if found else f"did not come within {timeout:g} s"
    return Result(
        True,
        f"waited for {text!r}: it {seen}",
        host,
        port,
        answer=_story(frames),
        found=found,
    )


def send(
    command,
    character=None,
    host=DEFAULT_HOST,
    port=None,
    dry_run=False,
    origin=DEFAULT_ORIGIN,
    settings=None,
    environ=None,
    sessions=None,
    answer=0,
    wait_for=None,
    timeout=30.0,
):
    """Send one line, or say why not. Never raises for a missing session.
    With answer > 0, stay attached that many seconds and return the
    story lines the game answered with in Result.answer. With
    `wait_for`, stay attached up to `timeout` seconds until a story
    line holds that text (Result.found says whether it came, #216)."""
    command = " ".join(str(command).split())
    if not command:
        return Result(False, "nothing to send", host, port, command)
    if port is None:
        port, why = resolve_port(character, sessions, host)
        if port is None:
            return Result(False, why, host, None, command)
    tier = "allowlisted (read-only)" if allowlisted(command) else "gated"
    if tier == "gated" and not gate_open(settings, environ):
        return Result(
            False,
            f"refused: {command!r} is not on the read-only allowlist and external "
            "sends are off - turn on 'allow external sends' in Settings, or set "
            "REVENANT_ALLOW_SEND=1 for this one call",
            host,
            port,
            command,
        )
    if dry_run:
        return Result(
            False,
            f"dry run: would send {command!r} to {host}:{port} ({tier})",
            host,
            port,
            command,
        )
    origin = "".join(ch for ch in origin if ch not in "\t\n\x1e") or DEFAULT_ORIGIN
    line = f"{EXTERNAL_MARK}{origin}\t{command}"
    if wait_for:
        frames = send_and_read(host, port, line, timeout, until=wait_for)
        if frames is None:
            return Result(
                False, f"nothing is listening on {host}:{port}", host, port, command
            )
        found = any(wait_for in text for text, stream, _ in frames if stream == "")
        seen = "came" if found else f"did not come within {timeout:g} s"
        return Result(
            True,
            f"sent {command!r} to {host}:{port} ({tier}); {wait_for!r} {seen}",
            host,
            port,
            command,
            answer=_story(frames),
            found=found,
        )
    if answer and answer > 0:
        frames = send_and_read(host, port, line, answer)
        if frames is None:
            return Result(
                False, f"nothing is listening on {host}:{port}", host, port, command
            )
        # The story, and the scripts' own echoes (the "script" stream:
        # "[soul] ..."), which are the answer when the line started a
        # script — a refusal echoed there was invisible here until
        # 2026-09-20, when a `;soul` read failed in three seconds
        # with nothing to show for it.
        story = "".join(text for text, stream, _ in frames if stream in ("", "script"))
        return Result(
            True,
            f"sent {command!r} to {host}:{port} ({tier})",
            host,
            port,
            command,
            answer=story,
        )
    if send_line(host, port, line):
        return Result(
            True, f"sent {command!r} to {host}:{port} ({tier})", host, port, command
        )
    return Result(False, f"nothing is listening on {host}:{port}", host, port, command)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="revenant-send", description=__doc__)
    parser.add_argument("command", nargs="*", help="the command, as you would type it")
    parser.add_argument(
        "--state",
        nargs="?",
        const="all",
        metavar="FIELDS",
        help="print the session's parsed state as JSON (all, or a comma list)",
    )
    parser.add_argument(
        "--wait-for",
        metavar="TEXT",
        help="stay attached until a story line holds TEXT (after the send, if any)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="how long --wait-for waits (default 30)",
    )
    parser.add_argument(
        "--character", help="which running character (default: the only one)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="say what would happen, send nothing"
    )
    parser.add_argument(
        "--origin",
        default=DEFAULT_ORIGIN,
        help="who is sending, for the echo and the log",
    )
    parser.add_argument(
        "--answer",
        type=float,
        default=0,
        metavar="SECONDS",
        help="stay attached this long after sending and print the game's answer",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument(
        "--port", type=int, help="a session port, bypassing the registry"
    )
    args = parser.parse_args(argv)
    command = " ".join(args.command)
    if not command and not args.wait_for and args.state is None:
        parser.error("a command, --state or --wait-for is needed")
    code = 0
    if command:
        result = send(
            command,
            character=args.character,
            host=args.host,
            port=args.port,
            dry_run=args.dry_run,
            origin=args.origin,
            answer=args.answer,
            wait_for=args.wait_for,
            timeout=args.timeout,
        )
        print(result.message)
        if result.answer:
            print(result.answer.rstrip("\n"))
        code = 0 if result.ok else 1
    elif args.wait_for:
        result = wait(
            args.wait_for,
            character=args.character,
            host=args.host,
            port=args.port,
            timeout=args.timeout,
        )
        print(result.message)
        if result.answer:
            print(result.answer.rstrip("\n"))
        code = 0 if result.found else 1
    if args.state is not None:
        fields = [] if args.state == "all" else args.state.split(",")
        result = query_state(
            character=args.character,
            host=args.host,
            port=args.port,
            fields=fields,
            origin=args.origin,
        )
        if result.state is None:
            print(result.message)
            code = 1
        else:
            print(json.dumps(result.state, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
