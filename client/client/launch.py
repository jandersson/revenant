"""One-command launcher: ensure a game session is running, attach the GUI.

- revenant              attach to a running session, spawning one first if needed
- revenant Testchar     attach to Testchar's session, or spawn one on a
                        free port — several characters run side by side,
                        one window each (#58)
- revenant --pick       the Start Menu shortcut's mode: a picker of
                        running sessions (attach) and every cached
                        character on every account (launch)
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
import keyring.errors

from client.login import (
    KEYRING_SERVICE,
    OTHER_ACCOUNT,
    LoginError,
    account_for_character,
    eaccess_protocol,
    fetch_character_list,
    keychain_password,
    load_login_defaults,
    save_login_defaults,
)
from client.session import DEFAULT_HOST, DEFAULT_PORT, running_sessions


def session_running(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def get_free_port(host, start=DEFAULT_PORT, tries=20):
    """The first port at or above `start` that nothing occupies —
    sessions run side by side, one port each (#58)."""
    for port in range(start, start + tries):
        if session_running(host, port):
            continue
        try:
            with socket.socket() as probe:
                probe.bind((host, port))
        except OSError:
            continue
        return port
    raise SystemExit(f"revenant: no free port in {start}..{start + tries - 1}")


def launch_choices(defaults, sessions):
    """The picker's menu: running sessions first (attach), then every
    cached character on every account that isn't already online. Each
    choice carries what acting on it needs — a port to attach, or a
    character/account pair to log in."""
    choices = []
    online = set()
    for entry in sorted(sessions, key=lambda e: e.get("port", 0)):
        name = str(entry.get("character") or f"port {entry.get('port')}")
        online.add(name.lower())
        choices.append(
            {
                "kind": "attach",
                "label": f"{name} — online, attach",
                "character": name,
                "port": entry["port"],
            }
        )
    accounts = defaults.get("accounts")
    if isinstance(accounts, dict) and accounts:
        rosters = [
            (entry.get("account") or key, entry.get("characters") or [])
            for key, entry in sorted(accounts.items())
        ]
    else:  # legacy flat cache from before per-account rosters
        rosters = [(defaults.get("account") or "", defaults.get("characters") or [])]
    label_accounts = len([1 for _, names in rosters if names]) > 1
    for account, names in rosters:
        for name in names:
            if name.lower() in online:
                continue
            label = f"{name} — {account}" if label_accounts else name
            choices.append(
                {
                    "kind": "launch",
                    "label": label,
                    "character": name,
                    "account": account,
                }
            )
    return choices


def gather_login(character, fresh_account=False, account=None):
    """Work out how the session will authenticate.

    Returns (account, character, key): key is None when the OS keychain
    holds the password (the session logs in by itself — and MUST be
    told the account, or it falls back to the saved default and logs
    the wrong one in; captured live, the Alvin-on-CRANCHU failure).
    Otherwise the password is collected — terminal prompt when there's
    a tty and the account and character are already known, the Qt login
    screen when not — and used exactly once for the handshake; only the
    single-use launch key survives. "Remember me" writes the password
    to the keychain and the account/character names to login.json, so
    future launches skip the dialog entirely. Env vars override the
    saved names.

    fresh_account (the picker's "Other account...") ignores every saved
    or env-provided identity and goes straight to the login screen. An
    explicit account (a picked character's owner) overrides both the
    env var and the saved default."""
    defaults = {} if fresh_account else load_login_defaults()
    account = (
        account
        or ("" if fresh_account else os.environ.get("REVENANT_ACCOUNT"))
        or defaults.get("account", "")
    )
    character = character or defaults.get("character", "")
    if account and character and keychain_password(account) is not None:
        return account, character, None

    error = ""
    remember = False
    while True:
        if account and character and sys.stdin.isatty():
            if error:
                print(f"revenant: {error}", file=sys.stderr)
            password = getpass.getpass(
                f"Password for {account} (used once, not stored): "
            )
        else:
            from client.gui.login_dialog import ask_credentials

            answer = ask_credentials(account, character, error)
            if answer is None:
                raise SystemExit(1)
            account, password, character, remember = answer
            if account and not password:
                # A blank password means "use the saved one" — adding an
                # already-remembered account's character mustn't demand
                # retyping a password the keychain holds (#58).
                password = keychain_password(account) or ""
            if not (account and password and character):
                error = "Account, password, and character are all required."
                continue
        try:
            key = eaccess_protocol(
                {
                    "username": account.encode("ASCII"),
                    "password": password.encode("ASCII"),
                    "character": character.capitalize(),
                }
            )
        except LoginError as exc:
            error = str(exc)
            continue
        if remember:
            try:
                keyring.set_password(KEYRING_SERVICE, account, password)
            except keyring.errors.KeyringError as exc:
                print(
                    f"revenant: couldn't save the password to the OS "
                    f"credential store: {exc}",
                    file=sys.stderr,
                )
            save_login_defaults(account, character)
        return account, character, key


def spawn_session(host, port, character, key=None, account=None):
    env = dict(os.environ, REVENANT_CHARACTER=character)
    if account:
        # The session's own login (the keychain-silent path) must use
        # the launcher's chosen account, not the saved default.
        env["REVENANT_ACCOUNT"] = account
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


def rebrand_for_dock():
    """macOS names the Dock entry after the interpreter, so the picker
    shows as "Python 3.12" without this: re-exec once under the
    Revenant-named interpreter symlink. The dialogs' application icon
    covers the Dock image; this covers the name."""
    interpreter = Path(sys.executable)
    if interpreter.name == "Revenant":
        return
    branded = branded_interpreter(interpreter)
    if branded != interpreter:
        os.execv(str(branded), [str(branded), "-m", "client.launch", *sys.argv[1:]])


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
    parser.add_argument(
        "--pick",
        action="store_true",
        help="choose the character from the account's roster before a new "
        "session spawns (the Start Menu shortcut's mode)",
    )
    parser.add_argument(
        "--list-characters",
        action="store_true",
        help="print the account's characters and exit (uses the saved "
        "account and keychain password)",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    if args.list_characters:
        defaults = load_login_defaults()
        account = os.environ.get("REVENANT_ACCOUNT") or defaults.get("account") or ""
        password = keychain_password(account) if account else None
        if not (account and password):
            raise SystemExit(
                "revenant: no saved account/password — log in once with "
                "remember checked, then retry"
            )
        for name in fetch_character_list(account, password):
            print(name)
        return

    if args.direct:
        if args.character:
            os.environ["REVENANT_CHARACTER"] = args.character
        return exec_gui([])

    if args.pick:
        if sys.platform == "darwin":
            rebrand_for_dock()
        return pick_and_go(args.host, args.port)

    if args.character:
        # The named character's session if one runs, a fresh session on
        # a free port otherwise — never someone else's window (#58).
        mine = next(
            (
                entry
                for entry in running_sessions(args.host)
                if str(entry.get("character", "")).lower() == args.character.lower()
            ),
            None,
        )
        if mine:
            return exec_gui(["--attach", f"{args.host}:{mine['port']}"])
        wanted = account_for_character(load_login_defaults(), args.character)
        account, character, key = gather_login(args.character, account=wanted)
        port = get_free_port(args.host, args.port)
        start_session(args.host, port, character, key, account)
        return exec_gui(["--attach", f"{args.host}:{port}"])

    if not session_running(args.host, args.port):
        account, character, key = gather_login(None)
        start_session(args.host, args.port, character, key, account)
    return exec_gui(["--attach", f"{args.host}:{args.port}"])


def start_session(host, port, character, key, account=None):
    print(f"revenant: starting a session for {character} on {host}:{port} ...")
    process = spawn_session(host, port, character, key=key, account=account)
    wait_for_session(process, host, port)


def pick_and_go(host, base_port):
    """--pick, the Start Menu shortcut's flow: choose a running session
    to attach or any cached character (any account) to launch on a free
    port. One window per pick — click the shortcut again for the next
    character (#58)."""
    defaults = load_login_defaults()
    choices = launch_choices(defaults, running_sessions(host))
    picked = OTHER_ACCOUNT  # nothing cached yet: straight to the login screen
    if choices:
        from client.gui.login_dialog import ask_character

        saved = (defaults.get("character") or "").lower()
        default_label = next(
            (c["label"] for c in choices if c["character"].lower() == saved),
            choices[0]["label"],
        )
        answer = ask_character([c["label"] for c in choices], default_label, "")
        if answer is None:
            return  # picker cancelled: no session, no GUI
        picked = (
            OTHER_ACCOUNT
            if answer is OTHER_ACCOUNT
            else next(c for c in choices if c["label"] == answer)
        )
    if picked is OTHER_ACCOUNT:
        account, character, key = gather_login("", fresh_account=True)
    elif picked["kind"] == "attach":
        return exec_gui(["--attach", f"{host}:{picked['port']}"])
    else:
        account, character, key = gather_login(
            picked["character"], account=picked["account"]
        )
    port = get_free_port(host, base_port)
    start_session(host, port, character, key, account)
    return exec_gui(["--attach", f"{host}:{port}"])


if __name__ == "__main__":
    main()
