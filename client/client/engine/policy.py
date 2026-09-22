"""What an outside sender may make the character do: the session's
command policy (#161, layer one).

Every line that reaches the session tagged with an origin — revenant-send,
an agent driving through it — passes `decide()` before the game sees
it; the player's own typing never does. Three tiers. Read-only verbs
always pass (the sendcmd allowlist). Verbs that give something away,
drop it, spend, leave or quit — DROP and DISCARD of anything but the
junk list, GIVE, HAND, OFFER of an item, SELL, TRADE, EXCHANGE, ACCEPT,
WITHDRAW, TRAIN and STUDY of a stat (TDPs; STUDY MY BOOK reads crafting
instructions and passes, 2026-09-22), DEPART, QUIT and EXIT, PUT into
anything but the character's own container, and `;reexec` — are
refused with a one-line reason the session echoes to every window. An
OFFER of an amount alone ("offer 62", "offer 62 kronars") is a catalog
merchant's bid, the line that closes an ORDER (HELP SHOPS), not a
hand-over, and passes (#234: the True Bard D'Or's apprentice gave up
on a refused bid, 2026-09-20). Everything else
passes; the client-side gate (allow_external_send / REVENANT_ALLOW_SEND)
still stands in front of it, so a passing line was still let through
deliberately. The policy is the session's, not the sender's: no origin
tag, claim or setting on the sending side lifts it.

A per-character file, ~/.revenant/policy/<name>.json (REVENANT_POLICIES
moves the directory), adjusts it: "deny" adds verbs, "allow" lifts
built-in ones — a denied verb, or "put" for the own-container rule
(an almsbox tithe, a teller's tray, #219); DROP of a non-junk item
and a valuable are never lifted — "patterns" adds regexes over the
whole line, and
"valuables" names item nouns an outsider may never drop, give, sell,
hand, offer, trade or put anywhere — the weapon, the armor, the
containers — whatever the verb. The file is the operator's live
control: PolicyStore re-reads it whenever its modification time
changes, so an "allow" added mid-session applies to the next line
(#206: an EXCHANGE allowed during a ferry test was refused by the
policy the session had read at its first outside command). Lich and Genie have no such gate; a
driver there is a script with full rights (docs/running.md).
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from client.game.discard import droppable

READ_ONLY = frozenset(
    {
        "info",
        "exp",
        "experience",
        "spell",
        "spells",
        "health",
        "wealth",
        "look",
        "time",
        "inventory",
        "inv",
        "glance",
        "assess",
        "tdp",
        "encumbrance",
        "enc",
        "strength",
        "reflex",
        "agility",
        "charisma",
        "discipline",
        "wisdom",
        "intelligence",
        "stamina",
        "premium",
    }
)

# Verb -> why an outsider does not get it. The reason is the echo.
DENIED = {
    "give": "GIVE hands something away",
    "hand": "HAND hands something away",
    "offer": "OFFER hands something away",
    "sell": "SELL spends an item",
    "trade": "TRADE spends an item",
    "exchange": "EXCHANGE spends coins or an item",
    "accept": "ACCEPT takes someone's offer",
    "withdraw": "WITHDRAW spends banked coins",
    "train": "TRAIN spends TDPs",
    "study": "STUDY of a stat spends TDPs",
    "depart": "DEPART is the character's own call",
    "quit": "QUIT is the character's own call",
    "exit": "EXIT is the character's own call",
    "discard": "DISCARD throws an item away",
    ";reexec": ";reexec stops every script",
}
# STUDY <stat> spends TDPs; STUDY MY BOOK (a crafting book's page, the
# alchemy kit's first evening, 2026-09-22) reads instructions and passes.
STATS = (
    "strength",
    "reflex",
    "agility",
    "charisma",
    "discipline",
    "wisdom",
    "intelligence",
    "stamina",
)


def _studies_a_stat(words):
    """True for STUDY alone or STUDY <stat ...>: the TDP spend."""
    return len(words) < 2 or words[1] in STATS


# OFFER <amount>, optionally with coin words, is a merchant's bid — ORDER
# quotes, OFFER closes (#234) — and hands nothing away; OFFER <item>
# stays a hand-over.
_BID = re.compile(
    r"^offer \d+(?: (?:copper|bronze|silver|gold|platinum|kronars?|lirums?|"
    r"dokoras?|coins?))*$"
)
# DROP: only the junk list (client/game/discard.py: grass, grass rope,
# settings.json droppable) is droppable; a valuable never.
DROP_VERBS = ("drop",)
# Verbs a valuable noun turns into a refusal even when allowed.
VALUABLE_VERBS = (
    "put",
    "drop",
    "give",
    "sell",
    "hand",
    "offer",
    "trade",
    "toss",
    "throw",
)


@dataclass
class Policy:
    denied: dict = field(default_factory=lambda: dict(DENIED))
    patterns: list = field(default_factory=list)  # compiled regexes
    valuables: tuple = ()
    allowed: tuple = ()  # the file's "allow" words, for the rules a verb lifts

    def decide(self, line):
        """(allowed, tier, reason) for one command line from outside."""
        return decide(line, self)


@dataclass
class Verdict:
    allowed: bool
    tier: str  # "read-only" | "denied" | "allowed"
    reason: str = ""


def policies_dir() -> Path:
    return Path(os.environ.get("REVENANT_POLICIES", "~/.revenant/policy")).expanduser()


def policy_path(character) -> Path:
    name = re.sub(r"[^a-z0-9]", "", str(character or "").lower()) or "default"
    return policies_dir() / f"{name}.json"


def load_policy(character) -> Policy:
    """The built-in policy adjusted by the character's file, if any; a
    file that will not read leaves the built-in policy standing."""
    denied = dict(DENIED)
    patterns = []
    valuables = []
    try:
        raw = json.loads(policy_path(character).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    for verb in _words(raw.get("deny")):
        denied.setdefault(verb, f"{verb.upper()} is denied by the policy file")
    allowed = tuple(_words(raw.get("allow")))
    for verb in allowed:
        denied.pop(verb, None)
    for pattern in raw.get("patterns") or []:
        try:
            patterns.append(re.compile(str(pattern), re.IGNORECASE))
        except re.error:
            continue
    valuables = tuple(_words(raw.get("valuables")))
    return Policy(
        denied=denied, patterns=patterns, valuables=valuables, allowed=allowed
    )


class PolicyStore:
    """Per-character policies, re-read when the file changes (#206):
    the file's modification time is kept beside the loaded policy, and
    a different stamp — or the file appearing or going — loads again."""

    def __init__(self):
        self._loaded = {}  # character -> (mtime_ns or None, Policy)

    def get(self, character) -> Policy:
        try:
            stamp = policy_path(character).stat().st_mtime_ns
        except OSError:
            stamp = None
        cached = self._loaded.get(character)
        if cached is None or cached[0] != stamp:
            cached = (stamp, load_policy(character))
            self._loaded[character] = cached
        return cached[1]


def _words(value):
    if isinstance(value, str):
        value = value.split(",")
    return [str(word).strip().lower() for word in value or [] if str(word).strip()]


def decide(line, policy=None) -> Verdict:
    policy = policy or Policy()
    words = line.strip().lower().split()
    if not words:
        return Verdict(True, "allowed")
    verb = words[0]
    if verb in READ_ONLY:
        return Verdict(True, "read-only")
    if (
        verb in policy.denied
        and not _BID.match(" ".join(words))
        and not (verb == "study" and not _studies_a_stat(words))
    ):
        return Verdict(False, "denied", policy.denied[verb])
    if verb in DROP_VERBS:
        item = _item(words[1:])
        if not droppable(item):
            return Verdict(
                False,
                "denied",
                f"DROP of {item or 'that'}: only the junk list is droppable "
                "(grass, grass rope, settings.json droppable)",
            )
    if (
        verb == "put"
        and "put" not in policy.allowed
        and " in " in f" {' '.join(words)} "
    ):
        # An explicit allow of put lifts this rule (#219: the almsbox
        # tithe); a valuable noun still refuses below.
        target = " ".join(words).split(" in ", 1)[1].split()
        if not target or target[0] != "my":
            return Verdict(False, "denied", "PUT into anything but your own container")
    if verb in VALUABLE_VERBS:
        for valuable in policy.valuables:
            if re.search(rf"\b{re.escape(valuable)}\b", " ".join(words)):
                return Verdict(False, "denied", f"{valuable} is a valuable")
    for pattern in policy.patterns:
        if pattern.search(line):
            return Verdict(
                False, "denied", f"the policy file denies /{pattern.pattern}/"
            )
    return Verdict(True, "allowed")


def _item(words):
    """The item noun of a DROP: "drop my grass rope" -> "grass rope"."""
    if words and words[0] == "my":
        words = words[1:]
    return " ".join(words)
