"""One-command launcher: ensure a game session is running, attach the GUI.

- revenant              attach to a running session, spawning one first if needed
- revenant Crannach     same, setting the character for a newly spawned session
- revenant --direct     single process: login and GUI together, no session
"""

import argparse
import getpass
import os
import socket
import subprocess
import sys
from pathlib import Path
from time import sleep, time

import keyring

from client.login import KEYRING_SERVICE, eaccess_protocol
from client.session import DEFAULT_HOST, DEFAULT_PORT


def session_running(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def resolve_credentials(character):
    """Work out how the session will authenticate.

    Returns (account, password): password is None when the OS keychain
    holds it (the session logs in by itself). With no keychain entry, the
    password is prompted for and used exactly once for the login
    handshake — the SGE-launcher model — never stored anywhere."""
    problems = []
    account = os.environ.get("REVENANT_ACCOUNT")
    if not account:
        problems.append(
            "REVENANT_ACCOUNT is not set (export REVENANT_ACCOUNT=YOURACCOUNT)"
        )
    if not character:
        problems.append(
            "no character given (revenant <Character>, or export REVENANT_CHARACTER)"
        )
    if problems:
        for problem in problems:
            print(f"revenant: {problem}", file=sys.stderr)
        raise SystemExit(1)
    if keyring.get_password(KEYRING_SERVICE, account) is not None:
        return account, None
    if not sys.stdin.isatty():
        print(
            f"revenant: no keychain password for {account} and no terminal "
            f"to prompt in (store it once with: uv run keyring set "
            f"{KEYRING_SERVICE} {account})",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return account, getpass.getpass(f"Password for {account} (used once, not stored): ")


def spawn_session(host, port, character, key=None):
    env = dict(os.environ, REVENANT_CHARACTER=character)
    command = [
        sys.executable,
        "-m",
        "client.session",
        "--host",
        host,
        "--port",
        str(port),
    ]
    # New process group: interrupting or closing the GUI must not take the
    # session (and with it the game connection) down too.
    if key is None:
        return subprocess.Popen(command, env=env, start_new_session=True)
    # A one-shot launch key travels over stdin: never in argv or env.
    process = subprocess.Popen(
        command + ["--key-stdin"],
        env=env,
        start_new_session=True,
        stdin=subprocess.PIPE,
        text=True,
    )
    process.stdin.write(key + "\n")
    process.stdin.close()
    return process


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


def branded_interpreter(interpreter: Path) -> Path:
    """A symlink to the interpreter named Revenant, so macOS derives the
    menu-bar/Dock name from it instead of "python3".

    It lives in .venv/branded/, not bin/: on macOS's case-insensitive
    filesystem, bin/Revenant would collide with the `revenant` console
    script, and CPython only detects the venv when pyvenv.cfg is in the
    executable directory's PARENT — so the symlink needs its own subdir.
    Falls back to the plain interpreter if anything is off.
    """
    branded = interpreter.parent.parent / "branded" / "Revenant"
    try:
        branded.parent.mkdir(exist_ok=True)
        if branded.is_symlink():
            if branded.resolve() != interpreter.resolve():
                branded.unlink()
                branded.symlink_to(interpreter)
        elif branded.exists():
            return interpreter  # not ours; leave it alone
        else:
            branded.symlink_to(interpreter)
        return branded
    except OSError:
        return interpreter


def exec_gui(gui_args):
    """Replace this process with the GUI (re-exec'd under the branded
    interpreter name on macOS; a proper .app bundle is issue #20)."""
    interpreter = Path(sys.executable)
    if sys.platform == "darwin":
        interpreter = branded_interpreter(interpreter)
    os.execv(
        str(interpreter),
        [str(interpreter), "-m", "client.gui.client_gui", *gui_args],
    )


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

    if args.direct:
        if args.character:
            os.environ["REVENANT_CHARACTER"] = args.character
        return exec_gui([])

    if not session_running(args.host, args.port):
        account, password = resolve_credentials(args.character)
        key = None
        if password is not None:
            key = eaccess_protocol(
                {
                    "username": account.encode("ASCII"),
                    "password": password.encode("ASCII"),
                    "character": args.character.capitalize(),
                }
            )
        print(f"revenant: starting a session on {args.host}:{args.port} ...")
        process = spawn_session(args.host, args.port, args.character, key=key)
        wait_for_session(process, args.host, args.port)
    elif args.character:
        print(
            f"revenant: session already running on {args.host}:{args.port}, "
            "attaching to it (character argument ignored)"
        )
    return exec_gui(["--attach", f"{args.host}:{args.port}"])


if __name__ == "__main__":
    main()
