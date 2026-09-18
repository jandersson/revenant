"""How ;scholarship books trains — these tests are the manual. It reads
every book on the library's shelves page by page, returns each with
STOW, stops at mind-lock, waits out a lap that taught nothing, and
returns the book in hand on a typed return (#210)."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import scholarship

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "scholarship_script", REPO / "scripts/scholarship.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

# Captured 2026-09-18 in the Paladins' Guild library.
SHELVES = (
    "Glancing over the contents of the shelves, you see the following titles:\n"
    "  TITLE                                        CALL LETTERS\n"
    "  --------------------------------             ------------\n"
    "  Introduction to the Guild of Paladins        IdsPG\n"
    "  A Night in Jail                              FtvNJ\n"
)
GOT = (
    'You get a copy of an ivory white book with gold leaf titled "Introduction '
    'to the Guild of Paladins".\n'
)
COVER = (
    "Glancing over the book's cover, you read:  Introduction to the Guild of "
    "Paladins\nYou get an urge to open it up and read the contents.\n"
)
OPENED = "You open your book.\n"
CONTENTS = (
    "Sir Darian's Introduction to the Guild of Paladins\nTABLE OF CONTENTS:\n"
    "  INTRODUCTION:             PAGE 2\n"
)
PAGE = "Reading:  INTRODUCTION:\n      Though I offer in this tome my own wisdom\n"
NOT_A_PAGE = "Reading: \n'17' is not a page in this book!\nType '?' to find out how to read a book.\n"
RETURNED = "You return the book to where it belongs.\n"
NO_SUCH = "I could not find what you were referring to.\n"


class Fake:
    """A library on a fake clock: books of `pages` pages by call letters;
    the Scholarship mindstate follows a script of values, one per page
    read; a typed "return" arrives at `stop_at`."""

    def __init__(self, mindstates, pages=None, stop_at=None, hostiles=None):
        self.mindstates = list(mindstates)
        self.pages = pages or {"IdsPG": 13, "FtvNJ": 3}
        self.stop_at = stop_at
        self.stopped = False
        self.now = 1000.0
        self.book = None
        self.reader = False
        self.sent, self.echoed, self.walks = [], [], []
        self.dead = False
        self.args = []
        self.status = SimpleNamespace(bleeding=False)
        self.state = SimpleNamespace(
            name="Lanival",
            experience={
                "Scholarship": {
                    "rank": 2,
                    "percent": 0,
                    "mindstate": self.mindstates.pop(0),
                }
            }
            if self.mindstates
            else {},
            hostiles=hostiles or {},
        )

    def _tick(self):
        if self.mindstates and self.state.experience:
            self.state.experience["Scholarship"]["mindstate"] = self.mindstates.pop(0)

    def ask(self, s, command, *_):
        self.sent.append(command)
        self.now += 2
        if command == "look shelves":
            return SHELVES
        if command.startswith("get "):
            letters = command[4:]
            if letters not in self.pages:
                return NO_SUCH
            self.book = letters
            return GOT
        if command == "read my book":
            if (
                self.reader is False
                and self.book
                and not getattr(self, "opened", False)
            ):
                return COVER
            self.reader = True
            return CONTENTS
        if command == "open my book":
            self.opened = True
            return OPENED
        if command.isdigit():
            assert self.reader, f"page {command} sent outside the reader"
            if int(command) <= self.pages[self.book] + 1:  # page 1 is the contents
                self._tick()
                return PAGE
            return NOT_A_PAGE
        if command == "q":
            assert self.reader, "Q sent outside the reader"
            self.reader = False
            return "[Paladins' Guild, Library]\n"
        if command == "stow my book":
            self.book, self.opened = None, False
            return RETURNED
        if command == "exp scholarship":
            return ""
        return ""

    def collect(self, s, seconds, until=None):
        self.now += seconds
        return ""

    def put(self, command):
        self.sent.append(command)

    def get(self, timeout=None, streams=("",)):
        return None

    def command(self, timeout=None):
        if self.stop_at is not None and not self.stopped and self.now >= self.stop_at:
            self.stopped = True
            return "return"
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        self.now += seconds


def walk(s, db, goals, describe="", avoid=()):
    s.walks.append(min(goals))
    return True


def run(fake, args=("books",), mapdb=None):
    script.clock = lambda: fake.now
    script.probe = SimpleNamespace(ask=fake.ask, collect=fake.collect)
    script.run(fake, script.parse_args(list(args)), mapdb=mapdb, walk_fn=walk)
    return "\n".join(fake.echoed)


def pages_sent(fake):
    return [c for c in fake.sent if c.isdigit()]


def test_the_shelves_table_parses_into_titles_and_call_letters():
    assert scholarship.parse_shelves(SHELVES) == [
        ("Introduction to the Guild of Paladins", "IdsPG"),
        ("A Night in Jail", "FtvNJ"),
    ]
    assert scholarship.parse_shelves(NO_SUCH) == []


def test_a_book_ends_at_not_a_page_or_a_blank_reading_line():
    assert scholarship.page_ended(NOT_A_PAGE)
    assert scholarship.page_ended("Reading:  \n")
    assert not scholarship.page_ended(PAGE)
    assert not scholarship.page_ended("")


def test_args():
    assert scholarship.parse_args([]) == {
        "mode": "books",
        "library": "",
        "until": 34,
        "once": False,
        "timer": 60,
    }
    options = scholarship.parse_args(
        ["books", "library=11716", "until=30", "once", "timer=45"]
    )
    assert options == {
        "mode": "books",
        "library": "11716",
        "until": 30,
        "once": True,
        "timer": 45,
    }
    assert scholarship.parse_args(["classes"])["mode"] == "classes"


def test_it_reads_every_book_page_by_page_and_returns_each():
    # Thirteen pages then the story's three; the lock comes on the last page.
    fake = Fake(mindstates=[0] + [1] * 13 + [34], stop_at=1000 + 600)
    out = run(fake, ["books", "once"])
    assert fake.sent[:6] == [
        "look shelves",
        "get IdsPG",
        "read my book",
        "open my book",
        "read my book",
        "2",
    ]
    first = fake.sent.index("stow my book")
    assert fake.sent[first - 1] == "q"
    assert fake.sent[first - 2] == "15"  # the fourteenth number: not a page
    assert fake.sent[first + 1] == "get FtvNJ"
    assert (
        "read 'Introduction to the Guild of Paladins', 13 page(s) — "
        "Scholarship 2 00% (0/34) → 2 00% (1/34)" in out
    )
    assert "Scholarship at 34/34 — done" in out or "34/34" in out


def test_the_lock_mid_book_closes_and_returns_it():
    fake = Fake(mindstates=[0, 5, 34] + [34] * 20, stop_at=1000 + 600)
    out = run(fake, ["books", "once"])
    assert pages_sent(fake) == ["2", "3"]
    assert fake.sent[-3:] == ["q", "stow my book"] or fake.sent[-2:] == [
        "q",
        "stow my book",
    ]
    assert "after 2 page(s)" in out
    assert "done" in out


def test_a_book_read_within_the_timer_is_skipped_and_the_lap_waits():
    # One lap reads both books; the next finds both within the timer
    # and waits for the first to run out; the return lands mid-wait.
    fake = Fake(mindstates=[0] * 40, stop_at=1000 + 500)
    out = run(fake, ["books", "timer=30"])
    assert fake.sent.count("get IdsPG") == 1
    assert fake.sent.count("get FtvNJ") == 1
    assert "every book read within the last 30 minutes" in out
    assert "stopping" in out


def test_after_the_timer_the_books_are_read_again():
    fake = Fake(mindstates=[0] * 80, stop_at=1000 + 4000)
    run(fake, ["books", "timer=30"])
    assert fake.sent.count("get IdsPG") >= 2


def test_a_typed_return_closes_the_reader_returns_the_book_and_ends():
    fake = Fake(mindstates=[0] * 40, stop_at=1000 + 12)
    out = run(fake, ["books"])
    assert fake.sent[-2:] == ["q", "stow my book"]
    assert fake.book is None
    assert "stopping" in out


def test_bleeding_waits_before_a_book():
    fake = Fake(mindstates=[0] * 40, stop_at=1000 + 200)
    fake.status.bleeding = True
    out = run(fake, ["books"])
    assert "bleeding" in out
    assert "get IdsPG" not in fake.sent


def test_hostiles_stop_it_between_books():
    fake = Fake(mindstates=[0] * 40, hostiles={"1": True})
    out = run(fake, ["books"])
    assert "hostiles in the room" in out
    assert "get IdsPG" not in fake.sent


def test_no_shelves_is_told_so():
    fake = Fake(mindstates=[0])
    fake.ask = lambda s, command, *_: (
        fake.sent.append(command) or NO_SUCH if command == "look shelves" else ""
    )
    out = run(fake, ["books"])
    assert "no shelves to read here" in out


def test_the_library_is_walked_to_first(monkeypatch, tmp_path):
    from client.game.mapdb import MapDB

    lib = MapDB([{"id": 11716, "uid": [1], "title": ["[Paladins' Guild, Library]"]}])
    fake = Fake(mindstates=[0, 34], stop_at=1000 + 60)
    run(fake, ["books", "library=11716", "once"], mapdb=lib)
    assert fake.walks == [11716]
    assert fake.sent[0] == "look shelves"


def test_classes_is_not_built_yet():
    fake = Fake(mindstates=[0])
    out = run(fake, ["classes"])
    assert "only `books` is built" in out
    assert fake.sent == []
