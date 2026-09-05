"""Open the experience-history dashboard in your browser:  ;beholder

Starts the beholder web dashboard (mindstate and rank over time, fed
by the always-on xp logger) if it isn't already running, then opens
http://127.0.0.1:8050. The dashboard is its own process and keeps
serving after the session ends — run ;beholder again any time for the
URL. It reads ~/.revenant/history.db, so history appears once the xp script
has logged for a minute or two.

Every session also runs  ;beholder quiet  automatically: it ensures
the server is up without opening a browser, so the dashboard is always
one bookmark (or one ;beholder) away. REVENANT_NO_BEHOLDER=1 disables
that autostart.
"""

import os
import socket
import subprocess
import webbrowser

HOST = "127.0.0.1"
PORT = 8050
URL = f"http://{HOST}:{PORT}"
WAIT_SECONDS = 15


def dashboard_running(host=HOST, port=PORT):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def spawn_dashboard():
    """Start `python -m beholder.app` detached and windowless; it owns
    its own lifetime (closing the session does not stop it)."""
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    from client.procspawn import command_for

    return subprocess.Popen(
        command_for("beholder.app"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


def main(s):
    # "quiet" (the session autostart): ensure the server, skip the browser.
    quiet = bool(s.args) and s.args[0] == "quiet"
    if dashboard_running():
        if not quiet:
            s.echo(f"dashboard already running: {URL}")
            webbrowser.open(URL)
        return
    s.echo("starting the dashboard ...")
    process = spawn_dashboard()
    for _ in range(WAIT_SECONDS * 2):
        if dashboard_running():
            s.echo(f"dashboard up: {URL}")
            if not quiet:
                webbrowser.open(URL)
            return
        if process.poll() is not None:
            s.echo(
                f"dashboard exited with code {process.returncode} — is the "
                "beholder package installed? (uv sync from the repo root)"
            )
            return
        s.sleep(0.5)
    s.echo(f"dashboard did not answer on {URL} after {WAIT_SECONDS}s")
