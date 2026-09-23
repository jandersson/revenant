"""What is new or addressed at the character, decided without Qt: the
seen-lines store, the scrub, the direct-address and spam tests
;sentinel runs on every line (#276). After dr-scripts'
status-monitor.lic (the detection, not its auto-reply).

A line is *addressed* when a bare-named someone — a player or a GM,
never an NPC with an article ("A young sacristan says to you, ...")
and never one of the operator's own characters — whispers, speaks,
thinks or gestures to you (`address`), when a word is spelled to slip
past a script's eye ("J_u_M_p", "jUmP": `hidden_command`), or when the
game's `ooc` stream relays a staff notice for this instance
("TWEET: ... #drprime" with no weekly-calendar wording: `broadcast`).
Those ring the bell at once. Everything else on the story stream goes
through the `Novelty` store: numerals and currency words scrubbed so
"worth 193 Kronars" is one line, boilerplate (exits, "Also here",
roundtimes) and lines naming a player present dropped, a line never
seen before flagged once as new and remembered
(`~/.revenant/sentinel/<name>.json`, written atomically), and two spam
shapes watched over the recent lines — the same line more than
UNIQUE times in the last WINDOW, or FREQUENCY near-duplicate lines
(Levenshtein under SIMILARITY percent) within SPAN seconds — the
thresholds status-monitor ships (4, 6, 70). Sources:
docs/bibliography.md.
"""

import json
import os
import re
from collections import Counter, deque
from pathlib import Path

UNIQUE = 4  # the same line more than this often in the last WINDOW lines
FREQUENCY = 6  # near-duplicate lines within SPAN seconds
SIMILARITY = 70  # percent: closer than this is a near-duplicate
WINDOW = 20
SPAN = 90.0
SETTLE = 600.0  # a line first seen this long ago is remembered for good
MAX_COMPARE = 160  # characters of a line the distance looks at

_SCRUBS = (
    re.compile(r"[0-9]+"),
    re.compile(
        r"\b(?:kronars?|lirums?|dokoras?|coppers?|bronze|silver|gold|platinum)\b",
        re.IGNORECASE,
    ),
)
_SPACES = re.compile(r"\s+")

# Story lines that are never news: the room's exits and company, the
# roundtime, the type-ahead wait, a prompt, a bracketed script line.
BOILERPLATE = tuple(
    re.compile(pattern)
    for pattern in (
        r"^Obvious (?:paths|exits):",
        r"^Also here:",
        r"^You also see",
        r"^Roundtime:",
        r"^\.\.\.wait",
        r"^\[",
        r"^>",
        r"^\*",
    )
)

# The streams whose lines are addressed at the character when a bare
# name speaks: the story, the game's whisper and talk windows, the
# gweth (thoughts) — "X thinks to you" is direct, the rest of the
# thoughts are chatter.
ADDRESS_STREAMS = frozenset({"", "whispers", "talk", "conversation", "thoughts"})

_NAME = r"(?P<name>[A-Z][a-z']+)"
ADDRESS = (
    ("whisper", re.compile(_NAME + r" whispers(?: to you)?[,:]")),
    (
        "speech",
        re.compile(_NAME + r" (?:says|asks|exclaims|shouts|yells|whispers) to you\b"),
    ),
    ("thought", re.compile(_NAME + r" thinks to you\b")),
    (
        "gesture",
        re.compile(
            _NAME + r" (?:pokes|taps|nudges|hugs|slaps|shoves|tickles|pats|prods|"
            r"kisses|pinches|tackles|kicks|punches|bites|licks|hits) you\b"
        ),
    ),
    (
        "gesture",
        re.compile(
            _NAME + r" (?:nods|waves|bows|smiles|winks|pokes|taps|nudges|beckons|"
            r"points|salutes|glances|stares|gazes|grins|peers|frowns|shrugs|"
            r"curtsies|hugs|slaps|shoves|tickles|pats|prods)\b[^.,!?]* (?:to|at) you\b"
        ),
    ),
)

# A word spelled so a script's regex misses it: letters split by
# separators ("J_u_M_p", "n-o-d") or a case that switches twice or more
# inside one word ("jUmP"), and once the separators are out a verb
# staff use for a presence check. status-monitor's command_check does
# the same against the game's whole verb list; this is the emote end
# of it, since a name like McDonald switches case too.
_SEPARATED = re.compile(r"(?<![A-Za-z])[A-Za-z](?:[_~=.\-][A-Za-z]){2,}(?![A-Za-z])")
_WORD = re.compile(r"[A-Za-z]{3,}")
CHECK_VERBS = frozenset(
    """
    nod jump wave bow smile dance bounce laugh sit stand kneel salute clap
    shrug frown wink giggle cheer applaud hug poke yawn sigh stare glance
    blink sneeze cough whistle hum sing ponder think tap stomp spin twirl
    hop skip kick punch yell shout scream cry weep growl snarl hiss purr
    meow bark howl roar blush grin smirk chuckle chortle snicker cackle
    tickle curtsy beckon point gasp faint wobble shiver sweat stretch
    scratch rub pat prod nudge shove slap kiss smooch snuggle pet flex
    strut lean lie sleep wake meditate pray chant count read write sign
    signal wag wiggle flap say ask tell answer look peer gaze speak talk
    whisper emote act agree disagree greet hello hail bye pout sulk
    """.split()
)

# The `ooc` stream's staff notices ("TWEET:  The war drums are sounding
# ... #drprime", 2026-09-23) name the instance in a hashtag; the weekly
# calendar notice ("Tuesday Tidings", 2026-09-20) is the one to skip.
INSTANCE = "#drprime"
CALENDAR = re.compile(r"tuesday tidings|check discord|this week", re.IGNORECASE)


def scrub(line):
    """The line as the store keys it: numerals and currency words out,
    whitespace collapsed, case folded; "" for nothing left."""
    text = line or ""
    for pattern in _SCRUBS:
        text = pattern.sub("", text)
    return _SPACES.sub(" ", text).strip().casefold()


def boilerplate(line):
    text = (line or "").strip()
    return not text or any(pattern.search(text) for pattern in BOILERPLATE)


def address(line, stream="", ignore=()):
    """The kind of direct address the line is — "whisper", "speech",
    "thought", "gesture" — from a bare-named speaker not in `ignore`
    (the operator's own characters), or None."""
    if stream not in ADDRESS_STREAMS:
        return None
    text = (line or "").strip()
    ignored = {str(name).strip().casefold() for name in ignore}
    for kind, pattern in ADDRESS:
        match = pattern.match(text)
        if match and match.group("name").casefold() not in ignored:
            return kind
    return None


def speaker(line):
    """The bare name that opens an addressed line, or None."""
    text = (line or "").strip()
    for _kind, pattern in ADDRESS:
        match = pattern.match(text)
        if match:
            return match.group("name")
    return None


def hidden_command(line):
    """A word spelled to slip past a script — "J_u_M_p", "jUmP" — or
    None."""
    text = line or ""
    for match in _SEPARATED.finditer(text):
        word = match.group(0)
        if re.sub(r"[_~=.\-]", "", word).casefold() in CHECK_VERBS:
            return word
    for match in _WORD.finditer(text):
        word = match.group(0)
        switches = sum(1 for a, b in zip(word, word[1:]) if a.isupper() != b.isupper())
        if (
            switches >= 2
            and not word.isupper()
            and not word.istitle()
            and word.casefold() in CHECK_VERBS
        ):
            return word
    return None


def broadcast(line, stream, instance=INSTANCE):
    """A staff notice for this instance on the `ooc` stream, calendar
    notices aside."""
    if stream != "ooc":
        return False
    text = line or ""
    return instance.casefold() in text.casefold() and not CALENDAR.search(text)


def newcomers(before, after):
    """The names in `after` that `before` lacked, in order."""
    known = {str(name).casefold() for name in before or ()}
    return [name for name in after or () if str(name).casefold() not in known]


def own_names(login):
    """The operator's own characters out of ~/.revenant/login.json —
    lines from them are never a stranger's address."""
    names = []
    if not isinstance(login, dict):
        return names
    current = login.get("character")
    if isinstance(current, str) and current.strip():
        names.append(current.strip())
    accounts = login.get("accounts")
    if isinstance(accounts, dict):
        for listed in accounts.values():
            if isinstance(listed, (list, tuple)):
                names.extend(str(name).strip() for name in listed if str(name).strip())
            elif isinstance(listed, dict):
                for name in listed.get("characters") or []:
                    if str(name).strip():
                        names.append(str(name).strip())
    seen = []
    for name in names:
        if name.casefold() not in {s.casefold() for s in seen}:
            seen.append(name)
    return seen


def distance(a, b):
    """Levenshtein distance between two strings, each cut to
    MAX_COMPARE characters."""
    a = (a or "")[:MAX_COMPARE]
    b = (b or "")[:MAX_COMPARE]
    if a == b:
        return 0
    if not a or not b:
        return len(a) + len(b)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        previous = current
    return previous[-1]


def near(a, b, similarity=SIMILARITY):
    """Whether two distinct lines are closer than `similarity` percent."""
    if a == b or not a:
        return False
    return distance(a, b) < len(a) * (100 - similarity) / 100


class Novelty:
    """The seen-lines store and the spam windows. `observe` answers
    ("new", line), ("spam", why) or None; `to_json` / `from_json`
    persist the lines settled as seen."""

    def __init__(self, seen=()):
        self.seen = set(seen)
        self.fresh = {}  # scrubbed line -> when first seen, not settled yet
        self.recent = deque(maxlen=WINDOW)
        self.stamps = []  # when the near-duplicate lines came
        self.dirty = False

    def settle(self, now):
        """Fresh lines older than SETTLE become seen for good."""
        for key, when in list(self.fresh.items()):
            if now - when > SETTLE:
                self.seen.add(key)
                del self.fresh[key]
                self.dirty = True

    def _reset(self):
        self.recent.clear()
        self.stamps = []

    def observe(self, line, now, names=()):
        """One story line: None when it is nothing, ("new", line) the
        first time a line is met, ("spam", why) when the recent lines
        repeat or rhyme past the thresholds."""
        if boilerplate(line):
            return None
        text = line.strip()
        lowered = text.casefold()
        if any(str(name).casefold() in lowered for name in names or () if name):
            return None
        key = scrub(text)
        if not key:
            return None
        self.settle(now)
        if key in self.seen:
            return None
        self.recent.append(key)
        counts = Counter(self.recent)
        if counts[key] > UNIQUE:
            self._reset()
            return (
                "spam",
                f"the same line {counts[key]} times in the last {WINDOW}: {text}",
            )
        if counts[key] == 1 and any(near(key, other) for other in self.recent):
            if not any(now - stamp < 0.5 for stamp in self.stamps):
                self.stamps = [stamp for stamp in self.stamps if now - stamp <= SPAN]
                self.stamps.append(now)
                if len(self.stamps) >= FREQUENCY:
                    self._reset()
                    return (
                        "spam",
                        f"{FREQUENCY} near-duplicate lines within {int(SPAN)} s: {text}",
                    )
        if key in self.fresh:
            return None
        self.fresh[key] = now
        self.dirty = True
        return ("new", text)

    def to_json(self):
        return {"seen": sorted(self.seen | set(self.fresh))}

    @classmethod
    def from_json(cls, data):
        seen = data.get("seen") if isinstance(data, dict) else None
        return cls(str(item) for item in seen or [] if isinstance(item, str))


def store_dir():
    return Path(
        os.environ.get("REVENANT_SENTINEL_DIR", "~/.revenant/sentinel")
    ).expanduser()


def _file(character):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", str(character or "unknown"))
    return store_dir() / f"{safe}.json"


def load(character):
    """The character's store, empty when there is none or the file is
    unreadable (never rewritten on a failed read until a save)."""
    try:
        with open(_file(character), encoding="utf-8") as handle:
            return Novelty.from_json(json.load(handle))
    except (OSError, ValueError):
        return Novelty()


def save(character, store):
    """The store written atomically: a temp file renamed into place."""
    path = _file(character)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(store.to_json(), handle)
    os.replace(temp, path)
    store.dirty = False
