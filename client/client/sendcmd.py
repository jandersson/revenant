"""Send one command into a running session from outside:  revenant-send

    revenant-send [--character NAME] [--dry-run] <command words ...>

The supported, audited way for a tool or an agent to act on what it
worked out - ";go2 bank", "exp all", ";stop hunt" - instead of handing
the line over to be retyped (#135). It resolves the character's session
through the registry the launcher keeps, sends the line tagged with its
origin, and the session echoes it to every attached window as
">> [external] <command>" and logs it, so a command that was not typed
by the player never acts invisibly.

Off by default, in two tiers. Read-only commands on the allowlist
(INFO, EXP, SPELL, HEALTH, WEALTH, LOOK, TIME, INVENTORY, GLANCE and the
;list / ;help / ;stop / ;sheet / ;clock scripts) go through whenever a
session is listening. Anything else - everything that spends, drops,
moves or attacks - needs the gate open: the "allow external sends"
setting (~/.revenant/settings.json, allow_external_send) or
REVENANT_ALLOW_SEND=1 for one call. --dry-run says what would happen
and sends nothing. Exit status 0 when the line went out (or a dry run),
1 when it was refused or nothing was listening.
"""

import argparse
import os
import sys
from dataclasses import dataclass

from client.session import DEFAULT_HOST, running_sessions, send_line
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

    @property
    def ok(self):
        """Exit-status sense: the line went out, or a dry run said its piece."""
        return self.sent or self.message.startswith("dry run")


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
        return None, "no session is running - nothing to send to"
    if character:
        wanted = character.strip().lower()
        for entry in sessions:
            if str(entry.get("character") or "").lower() == wanted:
                return int(entry["port"]), f"session for {entry['character']}"
        names = ", ".join(
            str(e.get("character") or f"port {e.get('port')}") for e in sessions
        )
        return None, f"no session is playing {character!r} (running: {names})"
    if len(sessions) == 1:
        entry = sessions[0]
        return int(
            entry["port"]
        ), f"session for {entry.get('character') or 'an unnamed character'}"
    names = ", ".join(
        str(e.get("character") or f"port {e.get('port')}") for e in sessions
    )
    return None, f"several sessions are running ({names}) - name one with --character"


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
):
    """Send one line, or say why not. Never raises for a missing session."""
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
    if send_line(host, port, f"{EXTERNAL_MARK}{origin}\t{command}"):
        return Result(
            True, f"sent {command!r} to {host}:{port} ({tier})", host, port, command
        )
    return Result(False, f"nothing is listening on {host}:{port}", host, port, command)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="revenant-send", description=__doc__)
    parser.add_argument("command", nargs="+", help="the command, as you would type it")
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
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument(
        "--port", type=int, help="a session port, bypassing the registry"
    )
    args = parser.parse_args(argv)
    result = send(
        " ".join(args.command),
        character=args.character,
        host=args.host,
        port=args.port,
        dry_run=args.dry_run,
        origin=args.origin,
    )
    print(result.message)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
