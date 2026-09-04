"""Capture a ;sheet snapshot for every cached character, one at a time.

Walks the characters that have no snapshot in xp.db yet: spawns each
one's session, opens a window on it, waits for `;sheet`'s
start-of-session snapshot to land, then **stops and waits for you** —
Enter moves to the next character, `s` skips, `q` quits. Nothing
advances on its own; looking around is the point (#111).

    uv run python tools/roster_sweep.py            # every pending character
    uv run python tools/roster_sweep.py Doc Testchar  # just these two
    uv run python tools/roster_sweep.py --all      # re-snapshot everyone
    uv run python tools/roster_sweep.py --list     # print the plan, do nothing

Why bother: `guild` only reaches xp.db's character table through
`;sheet`, so an un-snapshotted character is invisible to `;circle` and
to beholder's Circle-gates view.

Needs the account password in the OS keychain — the sweep never
prompts, so log in once with "remember me" first. Characters on the
same account are done in turn, since only one can be logged in at a
time.
"""

import argparse
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "client")]

from client.launch import get_free_port, spawn_session, wait_for_session  # noqa: E402
from client.login import account_for_character, load_login_defaults  # noqa: E402
from client.roster import pending_characters, snapshot_summary  # noqa: E402
from client.session import DEFAULT_HOST, DEFAULT_PORT, send_line  # noqa: E402

SNAPSHOT_TIMEOUT = 180  # ;sheet asks INFO and EXP ALL, re-asking what login noise ate
POLL_SECONDS = 2


def xp_db_path():
    return Path(os.environ.get("REVENANT_XP_DB", "~/.revenant/xp.db")).expanduser()


def snapshotted_names(path):
    """Character names already in the history, or an empty set when the
    database does not exist yet (nothing has ever been snapshotted)."""
    if not path.exists():
        return set()
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        return {
            row[0]
            for row in connection.execute(
                "select distinct character_name from character"
            )
        }


def latest_snapshot(path, character):
    """The newest snapshot timestamp for a character, or None."""
    if not path.exists():
        return None
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        row = connection.execute(
            "select max(logged_at) from character where lower(character_name) = ?",
            (character.lower(),),
        ).fetchone()
    return row[0] if row else None


def snapshot_counts(path, character, stamp):
    """(stats, skills) recorded in one snapshot.

    Printed beside the timestamp because a capture that stored no
    skills otherwise reads exactly like a complete one — an untrained
    character looks identical to a failure (#112).
    """
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        counts = [
            connection.execute(
                f"select count(*) from {table} "
                "where lower(character_name) = ? and logged_at = ?",
                (character.lower(), stamp),
            ).fetchone()[0]
            for table in ("stats", "sheet_skills")
        ]
    return tuple(counts)


def wait_for_snapshot(path, character, before, timeout=SNAPSHOT_TIMEOUT):
    """Block until a snapshot newer than `before` exists for the
    character. Returns its timestamp, or None on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        newest = latest_snapshot(path, character)
        if newest is not None and newest != before:
            return newest
        time.sleep(POLL_SECONDS)
    return None


def open_window(host, port):
    """A window on the session, so the character can be looked at. Not
    exec'd: the sweep has to outlive it and close it again."""
    return subprocess.Popen(
        [sys.executable, "-m", "client.gui.client_gui", "--attach", f"{host}:{port}"],
        cwd=str(REPO),
    )


LOGOUT_SECONDS = 5  # time for the game to act on QUIT before the process dies


def logout(host, port):
    """QUIT through the session, so the character actually leaves the
    game rather than going linkdead.

    Killing the session only drops the connection — the game warns
    about that at every login — and a lingering character can block the
    next one on the same account from logging in (#114). Best effort:
    a character the game has stopped answering for (an invalid-race
    login, say) may never process it, and terminate() below is the
    backstop either way."""
    if not send_line(host, port, "quit"):
        return False
    time.sleep(LOGOUT_SECONDS)
    return True


def close(process, what):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print(f"  {what} did not stop; killing it")
        process.kill()


def ask_next(character):
    """Enter advances, s skips the rest of this character, q quits.
    Anything else asks again — a stray keystroke must not end a sweep."""
    while True:
        try:
            answer = input(
                f"  {character} is up. Look around, then Enter for the next "
                "character (s=skip, q=quit): "
            )
        except EOFError:
            return "quit"
        answer = answer.strip().lower()
        if answer in ("", "n", "next"):
            return "next"
        if answer in ("s", "skip"):
            return "skip"
        if answer in ("q", "quit"):
            return "quit"
        print("  Enter, s, or q.")


def sweep_one(account, character, host, base_port, db):
    """One character: session up, window open, snapshot awaited, then
    the operator decides. Returns ("done"|"failed", verdict)."""
    before = latest_snapshot(db, character)
    port = get_free_port(host, base_port)
    print(f"  starting a session on {host}:{port} (account {account}) ...")
    session = window = None
    try:
        session = spawn_session(host, port, character, key=None, account=account)
        wait_for_session(session, host, port)
        window = open_window(host, port)
        print(f"  waiting for the ;sheet snapshot (up to {SNAPSHOT_TIMEOUT}s) ...")
        stamp = wait_for_snapshot(db, character, before)
        if stamp:
            stats, skills = snapshot_counts(db, character, stamp)
            # No skills is legitimate for an untrained character — say
            # so, rather than leaving it looking like a failure (#112).
            note = "" if skills else "  (no ranks yet — nothing to record)"
            print(f"  snapshot stored: {stats} stats, {skills} skills{note}")
        else:
            print("  no snapshot landed — moving on, nothing was stored")
        return ("done" if stamp else "failed"), ask_next(character)
    except SystemExit as exit_error:  # wait_for_session gives up this way
        print(f"  {character} failed to come up: {exit_error}")
        return "failed", "next"
    finally:
        close(window, "window")
        # QUIT before the kill, or the character is left linkdead and
        # may block the next one on this account (#114).
        if logout(host, port):
            print(f"  {character} logged out")
        close(session, "session")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="roster_sweep", description=__doc__)
    parser.add_argument(
        "characters", nargs="*", help="only these (default: all pending)"
    )
    parser.add_argument(
        "--all", action="store_true", help="include already-snapshotted characters"
    )
    parser.add_argument("--list", action="store_true", help="print the plan and exit")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    db = xp_db_path()
    defaults = load_login_defaults()
    done_already = snapshotted_names(db)
    total, done, waiting = snapshot_summary(defaults, done_already)
    print(f"roster: {total} cached characters, {done} snapshotted, {waiting} pending")

    if args.characters:
        plan = [
            (account_for_character(defaults, name) or "", name)
            for name in args.characters
        ]
    elif args.all:
        from client.roster import cached_characters

        plan = cached_characters(defaults)
    else:
        plan = pending_characters(defaults, done_already)

    unknown = [name for account, name in plan if not account]
    if unknown:
        raise SystemExit(
            "roster_sweep: no cached account owns "
            + ", ".join(unknown)
            + " — log that account in once so its roster is cached"
        )
    if not plan:
        print("nothing to do — every cached character has a snapshot")
        return
    print(f"plan: {len(plan)} character(s) — " + ", ".join(name for _, name in plan))
    if args.list:
        return

    results = {"done": [], "failed": [], "skipped": []}
    for index, (account, character) in enumerate(plan, start=1):
        print(f"\n[{index}/{len(plan)}] {character}")
        outcome, verdict = sweep_one(account, character, args.host, args.port, db)
        if verdict == "skip":
            results["skipped"].append(character)
        else:
            results[outcome].append(character)
        if verdict == "quit":
            print("\nstopping here.")
            break

    print("\n--- roster sweep ---")
    for label in ("done", "skipped", "failed"):
        names = results[label]
        print(f"  {label:<8} {len(names)}" + (f": {', '.join(names)}" if names else ""))


if __name__ == "__main__":
    main()
