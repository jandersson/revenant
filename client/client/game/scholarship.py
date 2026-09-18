"""Reading in a library — the model behind ;scholarship books (#210).

Scholarship trains by "reading books at a library" (Elanthipedia:
Scholarship skill); the RECALL forms the wiki also lists (Recall
command) registered nothing at rank 2 on 2026-09-18, and the books
did. A Lorethew library (the Paladins' Guild library is one; its
sign, READ SIGN, explains the system) lends by call letters: LOOK
SHELVES prints a table —

    Glancing over the contents of the shelves, you see the following titles:
      TITLE                                        CALL LETTERS
      --------------------------------             ------------
      Introduction to the Guild of Paladins        IdsPG
      A Night in Jail                              FtvNJ

— GET <letters> answers "You get a copy of an ivory white book with
gold leaf titled ...", READ MY BOOK "You get an urge to open it up and
read the contents.", OPEN MY BOOK "You open your book.", READ MY BOOK
again the table of contents and the page reader, in which a bare
number turns to that page ("Reading:  INTRODUCTION: ..."), a number
past the end answers "'17' is not a page in this book!" (a blank
"Reading:" line is the other end), "?" prints the reader's help and Q
closes the book. Q outside the reader is some other verb (it printed
the assist and referral status), so the script never sends it there.
STOW MY BOOK (or PUT ... IN MY <container>) returns the book: "You
return the book to where it belongs." — never a DROP.

Measured 2026-09-18 on a Paladin at Scholarship 2: four books (13,
about 3, 15 and 19 pages) took the skill to rank 4 at 24 percent in
about fifteen minutes; a book teaches per read, not per page (the
three-page story moved it as much as the thirteen-page introduction),
teaches nothing read again at once, and taught again 70 minutes later
(seven pages: rank 4 from 24 to 96 percent). The timer's length is
unmeasured; TIMER_MINUTES is the wait after a lap. The sign: "Please
do not read a book while bleeding, because you will NOT be able to
tend your wounds." Model: docs/training.md.
"""

import re

TIMER_MINUTES = 60  # the wait after a lap of the shelves: a book teaches once per timer
_SHELF_ROW = re.compile(r"^\s*(?P<title>\S.*?\S)\s{2,}(?P<letters>[A-Za-z]{3,})\s*$")
GOT = ("you get a copy",)
NO_SUCH = ("could not find", "what were you referring", "referring to")
URGE = ("urge to open",)
OPENED = ("you open",)
READING = "reading:"
NOT_A_PAGE = "is not a page in this book"
RETURNED = ("return the book",)


def parse_shelves(text):
    """[(title, call letters)] from LOOK SHELVES' table; [] when the
    answer is not a shelf listing."""
    books = []
    for line in (text or "").splitlines():
        match = _SHELF_ROW.match(line)
        if not match:
            continue
        title, letters = match.group("title"), match.group("letters")
        if title.upper() == "TITLE" or set(title) <= {"-"}:
            continue
        books.append((title, letters))
    return books


def page_ended(answer):
    """True when a page number's answer says the book is over: the
    "is not a page" line, or a "Reading:" line with nothing after it."""
    text = (answer or "").strip()
    lowered = text.lower()
    if NOT_A_PAGE in lowered:
        return True
    if not lowered.startswith(READING):
        return False
    return not text[len(READING) :].strip()


def parse_args(args):
    """{"mode", "library", "until", "once", "timer"} from ;scholarship's
    arguments: the first bare word is the mode ("books" by default)."""
    options = {
        "mode": "books",
        "library": "",
        "until": 34,
        "once": False,
        "timer": TIMER_MINUTES,
    }
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key == "library" and value:
            options["library"] = value
        elif sep and key in ("until", "timer") and value.isdigit():
            options[key] = int(value)
        elif key == "once":
            options["once"] = True
        elif key in ("books", "classes"):
            options["mode"] = key
    return options
