"""Dropbox sync (#547, #548, #549, #550): every machine's logs gathered in
Dropbox, filed by character — one checkbox in File → Settings, nothing
to run by hand.

With `dropbox_sync` on, each session autostarts ;dropbox, which every
INTERVAL_MINUTES copies into <Dropbox>/Revenant/:

    <Character>/<log>.<machine>.log    every log that is new there or has
                                       grown since the last copy, filed
                                       by the character it belongs to
    _other/<log>.<machine>.log         a log no character was found for

A character's folder holds its logs from every machine, each machine
named in the file; _other starts with an underscore, which no character
name can. A log whose name carries no character (one from before the
names did, late September 2026) is filed by best effort (#550,
owners()): the login line in it, else the log of the same stamp, else
the session before it — a ;reexec or a reconnect never logs in again,
so it continues the last session whose character is known.

The Dropbox folder is the one Dropbox's own info.json names
(Dropbox Help: "How to find the Dropbox folder on a computer"), the
personal account before a business one, else ~/Dropbox; the
`dropbox_dir` setting or REVENANT_DROPBOX_DIR names any other synced
folder instead. <machine> is the host name, or `dropbox_machine`.

The logs are append-only and named by character and start time, so two
machines never write the same file and copying them together loses
nothing. A copy goes to a temporary file moved into place, so a sync
never picks up half a log. Nothing in Dropbox is ever deleted, and each
machine keeps writing its own local files, so a sync problem never
touches a running session. Only the logs go: the history database
(history.db, the dashboard's) stays on its machine (#551).
"""

import bisect
import json
import os
import re
import shutil
import socket
from pathlib import Path

ENV = "REVENANT_DROPBOX_DIR"
FOLDER = "Revenant"  # inside the Dropbox folder: one folder per character below it
OTHER = "_other"  # the logs whose names carry no character
# The character a log's name carries: game-, lnet-, revenant_client- and
# drive-<Name>-<YYYYMMDD>-<HHMMSS> (client_logger.py, tools/drive.py).
_CHARACTER = re.compile(r"^[a-z_]+-([A-Za-z]+)-\d{8}-\d{6}")
_STAMP = re.compile(r"-(\d{8}-\d{6})")  # when the log's process started
# The login line, sent once when a character logs in (xml_data reads it).
_LOGIN = re.compile(r"""<app char=["']([A-Za-z]+)["']""")
SNIFF_BYTES = 256 * 1024  # how much of a log is read for its login line
_LOGINS = {}  # (path, size, mtime) -> the login found: each log read once a session
INTERVAL_MINUTES = 10  # between ;dropbox's copies


def info_files(home=None, environ=None):
    """Where Dropbox keeps info.json: ~/.dropbox/ on macOS and Linux,
    %APPDATA%\\Dropbox\\ or %LOCALAPPDATA%\\Dropbox\\ on Windows."""
    home = Path(home) if home is not None else Path.home()
    environ = os.environ if environ is None else environ
    places = [home / ".dropbox" / "info.json"]
    for variable in ("APPDATA", "LOCALAPPDATA"):
        if environ.get(variable):
            places.append(Path(environ[variable]) / "Dropbox" / "info.json")
    return places


def find_dropbox(home=None, environ=None):
    """The Dropbox folder on this computer, or None: the path info.json
    names (the personal account first), else ~/Dropbox when it exists."""
    home = Path(home) if home is not None else Path.home()
    for place in info_files(home, environ):
        try:
            accounts = json.loads(place.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for kind in ("personal", "business"):
            entry = accounts.get(kind) if isinstance(accounts, dict) else None
            path = entry.get("path") if isinstance(entry, dict) else None
            if path and Path(path).is_dir():
                return Path(path)
    fallback = home / "Dropbox"
    return fallback if fallback.is_dir() else None


def shared_dir(settings):
    """The folder synced between machines: REVENANT_DROPBOX_DIR, else
    the `dropbox_dir` setting, else the Dropbox folder found here; None
    when there is none."""
    value = os.environ.get(ENV) or str(settings.get("dropbox_dir") or "")
    if value.strip():
        return Path(value).expanduser()
    return find_dropbox()


def machine_name(settings, host=None):
    """This machine's folder name: the `dropbox_machine` setting, else
    the host name, lowercased, a trailing .local/.lan/.home dropped, and
    any run of characters but letters, digits, _ and - made one "-"."""
    value = str(settings.get("dropbox_machine") or "").strip()
    value = (value or host or socket.gethostname()).lower()
    value = re.sub(r"\.(local|lan|home)$", "", value)
    value = re.sub(r"[^a-z0-9_-]+", "-", value).strip("-")
    return value or "machine"


def character_of(name):
    """The character a log's file name carries, or None (a process
    before login, the legacy logs)."""
    match = _CHARACTER.match(name)
    return match.group(1).capitalize() if match else None


def tagged(name, machine):
    """The log's name with its machine before .log:
    game-Lanival-20261014-200000.calculon.log (a rotated debug log's
    .log.1 likewise)."""
    if ".log" in name:
        return name.replace(".log", f".{machine}.log", 1)
    return f"{name}.{machine}"


def stamp_of(name):
    """The YYYYMMDD-HHMMSS a log's name carries, or None (the old
    shared logs, revenant_client.log)."""
    match = _STAMP.search(name)
    return match.group(1) if match else None


def login_in(path):
    """The character whose login line is in the log's first SNIFF_BYTES,
    or None; each log is read once a session."""
    path = Path(path)
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime)
    if key not in _LOGINS:
        try:
            with open(path, "rb") as handle:
                head = handle.read(SNIFF_BYTES).decode("utf-8", "replace")
        except OSError:
            head = ""
        match = _LOGIN.search(head)
        _LOGINS[key] = match.group(1).capitalize() if match else None
    return _LOGINS[key]


def owners(paths):
    """{log name: character or None}, best effort (#550), in order: the
    character in the name; the login line in the log; the log of the
    same stamp (a revenant_client-<stamp>-<pid>.log is its game-<stamp>.log's);
    the nearest earlier log whose character is known (a log with no
    login continues the session before it), else the nearest later one.
    A log with no stamp in its name and no login line — the old shared
    revenant_client.log names several characters — stays None. Two
    characters played side by side before the names carried them are
    told apart by their login lines alone."""
    known = {path.name: character_of(path.name) or login_in(path) for path in paths}
    by_stamp, anchors = {}, []
    for name, who in known.items():
        stamp = stamp_of(name)
        if who and stamp:
            by_stamp.setdefault(stamp, who)
            anchors.append((stamp, who))
    anchors.sort()
    stamps = [stamp for stamp, _ in anchors]
    found = {}
    for name, who in known.items():
        stamp = stamp_of(name)
        if who is None and stamp and anchors:
            place = bisect.bisect_right(stamps, stamp)
            nearest = anchors[place - 1] if place else anchors[0]
            who = by_stamp.get(stamp) or nearest[1]
        found[name] = who
    return found


def log_target(root, name, machine, character=None):
    """Where a log goes: <root>/Revenant/<Character or _other>/<tagged>,
    the character owners() found, else the one its name carries."""
    folder = character or character_of(name) or OTHER
    return Path(root) / FOLDER / folder / tagged(name, machine)


def copy_logs(source, root, machine):
    """Every file in `source` (no subfolders, no dot-files) copied to its
    log_target — its character by owners() — when it is missing there, a
    different size, or newer: the names copied. A copy goes to a dot-file beside it first and is moved
    into place. Nothing in Dropbox is ever deleted — a debug log pruned
    locally after 7 days stays there."""
    source = Path(source)
    copied = []
    if not source.is_dir():
        return copied
    paths = [
        path
        for path in sorted(source.iterdir())
        if not path.name.startswith(".") and path.is_file()
    ]
    who = owners(paths)
    for path in paths:
        target = log_target(root, path.name, machine, who[path.name])
        target.parent.mkdir(parents=True, exist_ok=True)
        stray = Path(root) / FOLDER / OTHER / target.name
        if target.parent.name != OTHER and not target.exists() and stray.exists():
            # Filed under _other before its character was found: moved
            # to it, never copied twice (#550).
            os.replace(stray, target)
        here = path.stat()
        if target.exists():
            there = target.stat()
            if there.st_size == here.st_size and there.st_mtime >= here.st_mtime:
                continue
        part = target.with_name(f".{target.name}.part")
        shutil.copy2(path, part)  # the mtime too: the next look compares it
        os.replace(part, target)
        copied.append(path.name)
    return copied


def copy(root, machine, logs):
    """One copy of the logs into <root>/Revenant/: the names copied."""
    return copy_logs(logs, root, machine)
