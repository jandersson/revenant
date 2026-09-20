"""Train Scholarship by reading the library's books:  ;scholarship books

    ;scholarship books                read every book on the shelves, page by page, until mind-lock
    ;scholarship books library=11716  the library to read in (the profile's `library` otherwise; here if neither)
    ;scholarship books until=30       stop at that mindstate instead of 34
    ;scholarship books once           exit at mind-lock instead of holding for the drain
    ;scholarship books timer=45       minutes to wait after a lap of the shelves (a book teaches once per timer; 60)
    ;scholarship books wait=60        minutes the first timer may be off before the run ends instead (10)
    ;scholarship classes              not built yet: the plan is on #210
    ;scholarship return               (typed while it runs) return the book in hand and end

Reading a library's books trains Scholarship (Elanthipedia: Scholarship
skill; the wordings and the measurements are client/game/scholarship.py's).
The script walks to the library, LOOKs at the SHELVES for the titles and
their call letters, and for each book: GET <letters>, READ MY BOOK, OPEN
MY BOOK, READ MY BOOK into the page reader, then the page numbers one by
one until the book says a number is not a page, Q to close it, and STOW
MY BOOK, which the library takes as the return ("You return the book to
where it belongs."). The mindstate is read from the exp window after
every page — no command but a page number or Q goes out while the reader
is open, because the reader takes anything else for a page — and at
mind-lock the book is closed and returned and the script holds until
enough has drained to be worth reading again (`once` exits instead).
A book teaches once per timer, so a book read within the last `timer`
minutes is skipped — the read times are kept per character in
~/.revenant/scholarship/<name>.json, so the next run skips them too —
and when every book is, the script waits for the first timer to run
out if it is within `wait` minutes, and otherwise ends and says so,
so `;train` moves on to the next task and comes back (#255: the
reader idled 58 minutes of a 30-minute slot). It stops on death or hostiles
(the book returned first), waits out bleeding (the sign's warning), and
says so when the shelves are not a library's. ;train runs it as a task
(skills: ["Scholarship"], return_word "return"). Measured 2026-09-18:
four books, rank 2 to rank 4 in fifteen minutes; RECALL taught nothing.
Stop with:  ;stop scholarship (the book stays in hand — STOW it), or ;scholarship return.
"""

import re
import time

from client.engine.xml_data import LEARNING_RATES
from client.game import probe
from client.game.mapdb import MapDB
from client.game.scholarship import (
    GOT,
    NO_SUCH,
    OPENED,
    RETURNED,
    URGE,
    load_reads,
    page_ended,
    parse_args,
    parse_shelves,
    save_reads,
)
from client.game.walker import avoided_rooms, walk
from client.settings import load_settings

MIND_LOCK = 34
RESUME_BELOW = 28
LOCK_POLL = 30
BLEED_POLL = 30
MAX_PAGES = 200  # a book longer than this is a loop, not a book
COLLECT_SECONDS = 2
TAIL_SECONDS = 0.5
clock = time.monotonic  # tests replace it
wall = time.time  # the read times kept across runs (#255); tests replace it

_EXP_ANSWER = re.compile(r"Scholarship:\s+(\d+)\s+[\d.]+%\s+.*?\((\d+)/34\)")


def library_of(s):
    """The profile's library, a ;go2 target, or ""."""
    name = getattr(s.state, "name", None)
    if not name:
        return ""
    from client.game.profile import load_profile

    return str(load_profile(name).get("library") or "").strip()


def entry(s):
    return (getattr(s.state, "experience", None) or {}).get("Scholarship")


def mindstate(s):
    value = entry(s)
    return value["mindstate"] if value else None


def standing(s):
    """Scholarship as the exp window has it: "3 09% (1/34)", or "?"."""
    value = entry(s)
    if not value:
        return "?"
    return f"{value.get('rank', '?')} {value.get('percent', 0):02d}% ({value['mindstate']}/34)"


def ensure_mindstate(s):
    """The mindstate: the exp window's, or EXP SCHOLARSHIP's own answer
    when the window does not list the skill (a clear pool is absent)."""
    value = mindstate(s)
    if value is None:
        answer = probe.ask(s, "exp scholarship", COLLECT_SECONDS, TAIL_SECONDS)
        value = mindstate(s)
        if value is None:
            match = _EXP_ANSWER.search(answer or "")
            if match:
                value = int(match.group(2))
                # A whole entry, the parser's shape: a seed without a
                # rate took the session down at 04:30 on 2026-09-20,
                # thirty-six seconds into this script (#239).
                s.state.experience = dict(getattr(s.state, "experience", None) or {})
                s.state.experience["Scholarship"] = {
                    "rank": int(match.group(1)),
                    "percent": 0,
                    "mindstate": value,
                    "rate": LEARNING_RATES[min(value, 34)],
                }
    return value


def danger(s):
    if s.dead:
        return "you are dead"
    if getattr(s.state, "hostiles", None):
        return "hostiles in the room"
    return None


def bleeding(s):
    status = getattr(s, "status", None)
    return bool(getattr(status, "bleeding", False))


def wants_stop(s):
    while (line := s.command(timeout=0)) is not None:
        if "return" in line.lower():
            return True
    return False


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def pause(s, seconds):
    """Sleep in one-second slices; False when a typed return or danger
    arrived."""
    end = clock() + seconds
    while (left := end - clock()) > 0:
        s.sleep(min(1, left))
        if wants_stop(s) or danger(s):
            return False
    return True


def hold_at_lock(s, until):
    s.echo(f"scholarship: mind-locked ({until}/34) — holding until it drains")
    floor = min(RESUME_BELOW, until - 1)
    while True:
        if not pause(s, LOCK_POLL):
            return False
        value = mindstate(s)
        if value is not None and value <= floor:
            s.echo(f"scholarship: drained to {value}/34 — reading again")
            return True


def close_and_return(s, reading):
    """Q the reader when it is open, then STOW the book; True when the
    library took it back."""
    if reading:
        ask(s, "q")
    answer = ask(s, "stow my book").lower()
    if any(word in answer for word in RETURNED):
        return True
    s.echo("scholarship: the library did not take the book back — STOW it yourself")
    return False


def read_book(s, title, letters, options):
    """One book, cover to cover: "done" (returned), "target" (the
    mindstate reached `until`; the book returned), "stop" (a typed
    return or danger; the book returned), "missing" (no such book),
    "unknown" (an answer outside the tables; the book returned)."""
    before = standing(s)
    answer = ask(s, f"get {letters}").lower()
    if any(word in answer for word in NO_SUCH):
        s.echo(f"scholarship: no {letters!r} on the shelves — skipping {title!r}")
        return "missing"
    if not any(word in answer for word in GOT):
        s.echo(f"scholarship: GET {letters} answered nothing known — please report it")
        return "unknown"
    answer = ask(s, "read my book").lower()
    if any(word in answer for word in URGE):
        opened = ask(s, "open my book").lower()
        if not any(word in opened for word in OPENED):
            s.echo("scholarship: OPEN answered nothing known — please report it")
            close_and_return(s, reading=False)
            return "unknown"
        ask(s, "read my book")  # the table of contents: the reader is open now
    reading = True
    pages = 0
    for number in range(2, MAX_PAGES + 2):
        if danger(s) or wants_stop(s):
            close_and_return(s, reading)
            return "stop"
        answer = ask(s, str(number))
        if page_ended(answer):
            break
        pages += 1
        value = mindstate(s)
        if value is not None and value >= options["until"]:
            close_and_return(s, reading)
            s.echo(
                f"scholarship: {title!r} after {pages} page(s) — "
                f"Scholarship {before} → {standing(s)}"
            )
            return "target"
    close_and_return(s, reading)
    s.echo(
        f"scholarship: read {title!r}, {pages} page(s) — "
        f"Scholarship {before} → {standing(s)}"
    )
    return "done"


def run(s, options, mapdb=None, walk_fn=walk, avoid=()):
    if options["mode"] != "books":
        s.echo("scholarship: only `books` is built — the classes plan is on #210")
        return
    target = options["library"] or library_of(s)
    if target:
        if mapdb is None:
            s.echo("scholarship: the walk to the library needs the map — none loaded")
            return
        goals = mapdb.resolve(target)
        if not goals:
            s.echo(f"scholarship: nothing in the map matches library {target!r}")
            return
        if not walk_fn(s, mapdb, goals, describe=f"library {target!r}", avoid=avoid):
            s.echo("scholarship: could not reach the library — stopping")
            return
    if ensure_mindstate(s) is None:
        s.echo("scholarship: EXP shows no Scholarship — nothing to train")
        return
    books = parse_shelves(ask(s, "look shelves"))
    if not books:
        s.echo(
            "scholarship: no shelves to read here — a Lorethew library "
            "(library=<;go2 target>), or the profile's"
        )
        return
    s.echo(f"scholarship: {len(books)} book(s) on the shelves")
    # Call letters -> wall time of the last read, this run's and the
    # earlier ones' (#255: a fresh run re-read every book within its
    # timer and taught nothing); books gone from the shelves dropped.
    name = getattr(s.state, "name", None) or "unknown"
    shelved = {letters for _, letters in books}
    read_at = {k: v for k, v in load_reads(name).items() if k in shelved}
    while True:
        read_any = False
        for title, letters in books:
            since = wall() - read_at.get(letters, -float("inf"))
            if since < options["timer"] * 60:
                continue  # its timer is not up: it would teach nothing
            reason = danger(s)
            if reason:
                s.echo(f"scholarship: {reason} — stopping")
                return
            if wants_stop(s):
                s.echo("scholarship: stopping as asked")
                return
            while bleeding(s):
                s.echo("scholarship: bleeding — no reading until it stops (the sign)")
                if not pause(s, BLEED_POLL):
                    s.echo("scholarship: stopping")
                    return
            value = mindstate(s)
            if value is not None and value >= options["until"]:
                if options["once"]:
                    s.echo(f"scholarship: Scholarship at {value}/34 — done")
                    return
                if not hold_at_lock(s, options["until"]):
                    s.echo("scholarship: stopping")
                    return
            outcome = read_book(s, title, letters, options)
            if outcome == "stop":
                s.echo("scholarship: stopping")
                return
            if outcome in ("done", "target"):
                read_at[letters] = wall()
                save_reads(name, read_at)
                read_any = True
        if not read_any:
            oldest = min(read_at.values(), default=wall())
            wait = max(60.0, options["timer"] * 60 - (wall() - oldest))
            if wait > options["wait"] * 60:
                s.echo(
                    f"scholarship: every book read within the last "
                    f"{options['timer']} minutes — the first timer is "
                    f"{wait / 60:.0f} minutes off, ending (wait={options['wait']})"
                )
                return
            s.echo(
                f"scholarship: every book read within the last {options['timer']} "
                f"minutes — waiting {wait / 60:.0f} minutes for the first timer"
            )
            if not pause(s, wait):
                s.echo("scholarship: stopping")
                return


def main(s):
    options = parse_args(s.args or [])
    mapdb = MapDB.load() if (options["library"] or library_of(s)) else None
    avoid = avoided_rooms(mapdb, load_settings().get("avoid_rooms")) if mapdb else ()
    run(s, options, mapdb=mapdb, avoid=avoid)
