"""The hands (#407): what they hold off the parser's tags, a hand freed
by STOW — never DROP — with the answer judged, a weapon sheathed, and
the put-back a ;stop still sends.

    hands.held(s)                              # {"left": noun or None, "right": noun or None}
    hands.nouns(s)                             # the nouns held, left then right
    hands.holding(s, "bundle")                 # True when a hand holds that noun
    hands.full(s) / hands.empty(s)
    hands.free(s, keep=("mortar", "pestle"), ask=ask)   # STOW what is not kept; the nouns that went
    hands.free_one(s, keep=(), ask=ask)        # both full: the first not kept STOWed; True once a hand is free
    hands.stow(s, noun, ask=ask)               # one STOW, True unless the answer refused it
    hands.sheathe(s, weapon, container, ask=ask)   # SHEATHE into the container; STOW when the game asks where
    hands.at_end(s, ("pestle", "mortar"))      # a finally's put-backs: STOW each still held, as cleanup puts

Twenty places read the hand tags their own way and a dozen freed a
hand each its own way (a keep-list, the left only, a cascade), and
five put things back at a `;stop` (#395 came from one that did not).
A script passes its own `ask` so a test's fake answers the STOW; the
parser's hand state lags the answer, so the answer is the judge of a
stow, never the tags right after it.
"""

from client.game import act

SIDES = ("left", "right")
# What a refused STOW says beyond the not-found wordings: the container
# is full, the game will not ("You can't do that while ..."), or it
# asks what ("Stow what?").
STOW_REFUSED = ("no room", "any more room", "won't fit", "can't", "cannot", "stow what")
# SHEATHE with no container named and nothing remembered from a WIELD
# (captured 2026-09-22): "Sheathe your steel scimitar where?"
SHEATHE_WHERE = ("where?",)


def tags(s):
    """{"left": tag, "right": tag}: the parser's hand tags ({noun, name,
    exist}), None for an empty hand or a handle without hand state."""
    state = getattr(s, "state", None)
    found = {}
    for side in SIDES:
        tag = getattr(state, f"{side}_hand", None)
        found[side] = tag if isinstance(tag, dict) and tag.get("noun") else None
    return found


def held(s):
    """{"left": noun, "right": noun}, None for an empty hand."""
    return {side: (tag or {}).get("noun") or None for side, tag in tags(s).items()}


def nouns(s):
    """The nouns held, left then right."""
    return [noun for noun in held(s).values() if noun]


def _same(noun, wanted):
    """The game's noun is the last word, whatever adjectives either side
    carries ("bundling rope" is a rope)."""
    return str(noun).split()[-1].lower() == str(wanted).split()[-1].lower()


def holding(s, noun):
    """True when a hand holds `noun`."""
    return any(_same(held_noun, noun) for held_noun in nouns(s))


def side_of(s, noun):
    """ "left" or "right" for the hand holding `noun`, else None."""
    for side, held_noun in held(s).items():
        if held_noun and _same(held_noun, noun):
            return side
    return None


def full(s):
    return all(held(s).values())


def empty(s):
    return not any(held(s).values())


def refused(answer):
    """True when a STOW's or SHEATHE's answer refused it."""
    lowered = str(answer or "").lower()
    return act.missing(answer) or any(word in lowered for word in STOW_REFUSED)


def _mine(noun):
    """ "my <noun>", or the bare id when `noun` is one ("#136104233",
    items.name's form for a held item: the game takes an id bare)."""
    noun = str(noun)
    return noun if noun.startswith("#") else f"my {noun}"


def stow(s, noun, ask=None):
    """STOW MY <noun> (STOW #id for an id); True unless the answer
    refused it. Never a DROP."""
    return not refused((ask or act.ask)(s, f"stow {_mine(noun)}"))


def free(s, keep=(), ask=None):
    """STOW whatever a hand holds that is not in `keep`, left first; the
    nouns that went."""
    stowed = []
    for noun in nouns(s):
        if not any(_same(noun, kept) for kept in keep) and stow(s, noun, ask):
            stowed.append(noun)
    return stowed


def free_one(s, keep=(), ask=None):
    """A hand for something: True at once when one is empty; with both
    full, the first held noun not in `keep` (left first) STOWed, and
    True when that went; False when nothing would."""
    if not full(s):
        return True
    for noun in nouns(s):
        if not any(_same(noun, kept) for kept in keep):
            return stow(s, noun, ask)
    return False


def sheathe(s, weapon, container="", ask=None):
    """SHEATHE the weapon into its container, or — none named — where
    WIELD drew it from; "Sheathe your ... where?" (nothing remembered)
    falls back to STOW. True unless the answer refused it."""
    ask = ask or act.ask
    command = (
        f"sheathe my {weapon} in my {container}"
        if container
        else f"sheathe my {weapon}"
    )
    answer = ask(s, command)
    if any(word in answer.lower() for word in SHEATHE_WHERE):
        return stow(s, weapon, ask)
    return not refused(answer)


def cleanup(s, command):
    """A put that still goes out after a ;stop (the handle's cleanup
    flag; a handle without it takes the plain put)."""
    try:
        s.put(command, cleanup=True)
    except TypeError:
        s.put(command)


def at_end(s, wanted):
    """For a finally: STOW each noun of `wanted` a hand still holds, as
    cleanup puts (nothing read — after a ;stop every read raises); the
    nouns sent. Nothing for a dead character."""
    if getattr(s, "dead", False):
        return []
    sent = []
    for noun in nouns(s):
        if any(_same(noun, want) for want in wanted):
            cleanup(s, f"stow {_mine(noun)}")
            sent.append(noun)
    return sent
