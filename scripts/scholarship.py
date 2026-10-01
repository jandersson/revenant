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
The script walks to the library, LOOKs at the SHELVES (and the BOOKCASE,
where a library has both — the Asemath Academy's 55 books sit on two,
#256) for the titles and their call letters, and for each book: GET <letters>, READ MY BOOK, OPEN
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
reader idled 58 minutes of a 30-minute slot). The loop is every
trainer's (client/game/trainer.py): it stops on death or hostiles (the
book returned first, then the shared escape), waits out bleeding (the
sign's warning), and says so when the shelves are not a library's.
;train runs it as a task (skills: ["Scholarship"], return_word
"return"). Measured 2026-09-18:
four books, rank 2 to rank 4 in fifteen minutes; RECALL taught nothing.
Stop with:  ;stop scholarship (the book stays in hand — STOW it), or ;scholarship return.
"""

import time

from client.game import trainer, travel
from client.game.act import ask, unknown
from client.game.loop import danger, exp_entry, mindstate, pause, wants_stop
from client.game.scholarship import (
    GOT,
    NO_SUCH,
    OPENED,
    READING,
    RETURNED,
    URGE,
    load_reads,
    page_ended,
    parse_args,
    parse_shelves,
    save_reads,
)
from client.game.walker import walk

MIND_LOCK = 34
BLEED_POLL = 30
MAX_PAGES = 200  # a book longer than this is a loop, not a book
wall = time.time  # the read times kept across runs (#255); tests replace it


def library_of(s):
    """The profile's library, a ;go2 target, or ""."""
    name = getattr(s.state, "name", None)
    if not name:
        return ""
    from client.game.profile import load_profile

    return str(load_profile(name).get("library") or "").strip()


def standing(s):
    """Scholarship as the exp window has it: "3 09% (1/34)", or "?"."""
    value = exp_entry(s, "Scholarship")
    if not value:
        return "?"
    return f"{value.get('rank', '?')} {value.get('percent', 0):02d}% ({value['mindstate']}/34)"


def bleeding(s):
    status = getattr(s, "status", None)
    return bool(getattr(status, "bleeding", False))


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
        unknown(s, "scholarship", f"GET {letters}", answer)
        return "unknown"
    answer = ask(s, "read my book").lower()
    if any(word in answer for word in URGE):
        opened = ask(s, "open my book").lower()
        if not any(word in opened for word in OPENED):
            unknown(s, "scholarship", "OPEN", opened)
            close_and_return(s, reading=False)
            return "unknown"
        ask(s, "read my book")  # the table of contents: the reader is open now
    reading = True
    pages = 0
    reopened = False
    for number in range(2, MAX_PAGES + 2):
        if danger(s) or wants_stop(s):
            close_and_return(s, reading)
            return "stop"
        answer = ask(s, str(number))
        if not page_ended(answer) and READING not in answer.lower():
            # Not in the reader: a bare number is a command to the game
            # ("Please rephrase that command." 481 times on 2026-09-21,
            # #258). OPEN and READ once more; a book still not in the
            # reader is returned and reported, never paged blind.
            if not reopened:
                reopened = True
                ask(s, "open my book")
                ask(s, "read my book")
                answer = ask(s, str(number))
            if not page_ended(answer) and READING not in answer.lower():
                close_and_return(s, reading=False)
                unknown(s, "scholarship", f"{title!r} page {number}", answer)
                return "unknown"
        if page_ended(answer):
            break
        pages += 1
        value = mindstate(s, "Scholarship")
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
    """The trainer loop (client/game/trainer.py) with one step: the next
    book of the lap, read cover to cover — a book inside its timer
    passed over, a lap that taught nothing waited out or the end."""
    if options["mode"] != "books":
        s.echo("scholarship: only `books` is built — the classes plan is on #210")
        return
    target = options["library"] or library_of(s)
    if target:
        if mapdb is None:
            s.echo("scholarship: the walk to the library needs the map — none loaded")
            return
        if not travel.go(
            s, target, f"library {target!r}", db=mapdb, walk=walk_fn, avoid=avoid
        ):
            s.echo("scholarship: could not reach the library — stopping")
            return
    books = parse_shelves(ask(s, "look shelves"))
    # A library may shelve on more than one piece (#256: the Asemath
    # Academy's 18 books on the shelf and 37 on the bookcase); a room
    # without a bookcase refuses, which parses to no rows.
    shelved = {letters for _, letters in books}
    books += [b for b in parse_shelves(ask(s, "look bookcase")) if b[1] not in shelved]
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
    pending = []  # the books of this lap still to visit
    lap = {"count": 0, "read_any": False}

    def step(s):
        if not pending:
            if lap["count"] and not lap["read_any"]:
                oldest = min(read_at.values(), default=wall())
                wait = max(60.0, options["timer"] * 60 - (wall() - oldest))
                if wait > options["wait"] * 60:
                    return (
                        f"every book read within the last {options['timer']} "
                        f"minutes — the first timer is {wait / 60:.0f} minutes "
                        f"off (wait={options['wait']})"
                    )
                s.echo(
                    f"scholarship: every book read within the last "
                    f"{options['timer']} minutes — waiting {wait / 60:.0f} "
                    "minutes for the first timer"
                )
                if not pause(s, wait):
                    return None  # the loop says why
            pending.extend(books)
            lap["count"] += 1
            lap["read_any"] = False
        title, letters = pending.pop(0)
        since = wall() - read_at.get(letters, -float("inf"))
        if since < options["timer"] * 60:
            return None  # its timer is not up: it would teach nothing
        while bleeding(s):
            s.echo("scholarship: bleeding — no reading until it stops (the sign)")
            if not pause(s, BLEED_POLL):
                return None  # the loop says why
        outcome = read_book(s, title, letters, options)
        if outcome in ("done", "target"):
            read_at[letters] = wall()
            save_reads(name, read_at)
            lap["read_any"] = True
        return None  # "stop": the book is back, and the loop says why

    return trainer.train(
        s,
        "scholarship",
        "Scholarship",
        step,
        until=options["until"],
        once=options["once"],
        again="reading again",
        ask=ask,
    )


def main(s):
    options = parse_args(s.args or [])
    mapdb = travel.mapdb() if (options["library"] or library_of(s)) else None
    avoid = travel.avoided(mapdb) if mapdb else ()
    run(s, options, mapdb=mapdb, avoid=avoid)
