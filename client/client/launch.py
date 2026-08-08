"""One-command launcher: ensure a game session is running, attach the GUI.

- revenant              attach to a running session, spawning one first if needed
- revenant Crannach     same, setting the character for a newly spawned session
- revenant --direct     single process: login and GUI together, no session
"""
import argparse
import os
import socket
import subprocess
import sys
from time import sleep, time

import keyring

from client.login import KEYRING_SERVICE
from client.session import DEFAULT_HOST, DEFAULT_PORT


def session_running(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def ensure_credentials(character):
    """Fail fast with instructions — a background session cannot prompt."""
    problems = []
    account = os.environ.get("REVENANT_ACCOUNT")
    if not account:
        problems.append(
            "REVENANT_ACCOUNT is not set (export REVENANT_ACCOUNT=YOURACCOUNT)"
        )
    elif keyring.get_password(KEYRING_SERVICE, account) is None:
        problems.append(
            f"no keychain password for {account} (store it once with: "
            f"uv run keyring set {KEYRING_SERVICE} {account})"
        )
    if not character:
        problems.append(
            "no character given (revenant <Character>, or export REVENANT_CHARACTER)"
        )
    if problems:
        for problem in problems:
            print(f"revenant: {problem}", file=sys.stderr)
        raise SystemExit(1)


def spawn_session(host, port, character):
    env = dict(os.environ, REVENANT_CHARACTER=character)
    # New process group: interrupting or closing the GUI must not take the
    # session (and with it the game connection) down too.
    return subprocess.Popen(
        [sys.executable, "-m", "client.session", "--host", host, "--port", str(port)],
        env=env,
        start_new_session=True,
    )


def wait_for_session(process, host, port, timeout=60):
    deadline = time() + timeout
    while time() < deadline:
        if session_running(host, port):
            return
        if process.poll() is not None:
            raise SystemExit(
                f"revenant: session exited with code {process.returncode} "
                "before it came up (login failure?)"
            )
        sleep(0.2)
    raise SystemExit(f"revenant: no session on {host}:{port} after {timeout}s")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="revenant", description=__doc__)
    parser.add_argument(
        "character",
        nargs="?",
        default=os.environ.get("REVENANT_CHARACTER"),
        help="character for a newly spawned session (default: REVENANT_CHARACTER)",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="login and GUI in one process, without a detachable session",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    from client.gui import client_gui  # deferred: pulls in PyQt6

    if args.direct:
        if args.character:
            os.environ["REVENANT_CHARACTER"] = args.character
        return client_gui.main([])

    if not session_running(args.host, args.port):
        ensure_credentials(args.character)
        print(f"revenant: starting a session on {args.host}:{args.port} ...")
        process = spawn_session(args.host, args.port, args.character)
        wait_for_session(process, args.host, args.port)
    elif args.character:
        print(
            f"revenant: session already running on {args.host}:{args.port}, "
            "attaching to it (character argument ignored)"
        )
    return client_gui.main(["--attach", f"{args.host}:{args.port}"])


if __name__ == "__main__":
    main()
