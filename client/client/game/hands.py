"""The hands: what they hold, a hand freed by STOW (never DROP), the
put-back a ;stop still sends.

    hands.held(s)                                # {"left": noun, "right": noun}, None for empty
    hands.holding(s, "bundle")                   # also full(s), empty(s), nouns(s), tags(s), side_of(s, noun), tag_of(s, noun)
    since = hands.mark(s)                        # before a STOW straight off the ground, then
    hands.passed_through(s, since, "box")        # the box's tag, though the hand emptied (#423)
    hands.free(s, keep=("mortar",), ask=ask)     # STOW what is not kept; the nouns that went
    hands.free_one(s, ask=ask)                   # both full: the first STOWed; True once a hand is free
    hands.stow(s, noun, ask=ask)                 # one STOW, True unless refused; no room → PUT into the default container
    hands.stow_said(s, noun, ask=ask)            # the same, with the line that decided it (a refusal to quote)
    hands.sheathe(s, weapon, container, ask=ask) # where WIELD drew it from; asked where, the container, else STOW
    hands.at_end(s, ("pestle", "mortar"))        # a finally's STOWs, as cleanup puts

Pass the script's ask so a test's fake answers the STOW. The answer is
the judge, never the tags right after it (they lag); an id ("#123")
goes out bare.
"""

from client.game import act

_NOTES = """
Twenty places read the hand tags their own way and a dozen freed a hand
each its own way (a keep-list, the left only, a cascade) before #407;
five put things back at a ;stop, and #395 came from one that did not.

A STORE container with no room refuses the STOW and the item stays in
hand — the game does not fall back (captured 2026-09-26 with STORE
BOXES, "You pick up a reinforced oaken chest. There isn't any more room
in the sack for that.", and 2026-10-02 with STORE HERBS set to a herb
bag, "There isn't any more room in the bag for that.", the leaves still
held). Eight herb STOWs in ;remedies and one in ;heal read no answer,
so a full bag left the stack in hand and the next GET had no hand for
the pestle (#416). The operator, 2026-10-02: scripts must not fail on
it — so stow() PUTs into the default container, read once a run from
STORE DEFAULT ("         Default:  a rugged backpack").
"""

SIDES = ("left", "right")
# What a refused STOW says beyond the not-found wordings: the container
# is full, the game will not ("You can't do that while ..."), or it
# asks what ("Stow what?").
STOW_REFUSED = (
    "no room",
    "any more room",
    "won't fit",
    "wealth of gems",
    "can't",
    "cannot",
    "stow what",
)
# The refusals that mean the STORE container is full — the item then
# goes into the default container (#416). A full gem pouch says it its
# own way (captured 2026-10-03, #436): "You've already got a wealth of
# gems in there!  You'd better tie it up before putting more gems
# inside." — never TIEd here (#283), the gem goes to the default.
STOW_FULL = ("no room", "any more room", "won't fit", "wealth of gems")
_DEFAULTS = {}  # character -> the default container's noun, off STORE DEFAULT
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


def tag_of(s, noun):
    """The hand tag ({noun, name, exist}) of the hand holding `noun`, else None."""
    side = side_of(s, noun)
    return tags(s)[side] if side else None


def mark(s):
    """The parser's count of hand tags that named an item, now: the
    mark passed_through reads from (0 for a session without it)."""
    return getattr(getattr(s, "state", None), "hand_events", 0) or 0


def passed_through(s, since, noun):
    """The tag ({noun, name, exist}) of the last `noun` a hand named
    after the mark `since`, else None — the item a STOW took straight
    off the ground, which shows in a hand tag and empties it on the same
    line (#423). A session started before the parser kept them (an
    engine edit: relaunch) answers None."""
    last = getattr(getattr(s, "state", None), "last_held", None) or {}
    found = [
        tag
        for tag in last.values()
        if isinstance(tag, dict)
        and (tag.get("seq") or 0) > since
        and tag.get("noun")
        and _same(tag["noun"], noun)
    ]
    return max(found, key=lambda tag: tag["seq"]) if found else None


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


def default_container(s, ask=None):
    """The noun of the game's default container ("backpack"), off STORE
    DEFAULT's "Default:  a rugged backpack" line, read once a run per
    character; None when the answer names none."""
    character = str(getattr(getattr(s, "state", None), "name", "") or "")
    if character in _DEFAULTS:
        return _DEFAULTS[character]
    answer = (ask or act.ask)(s, "store default")
    noun = None
    for line in str(answer or "").splitlines():
        if "default" in line.lower() and ":" in line:
            words = line.split(":", 1)[1].split()
            if words and "not set" not in line.lower():
                noun = words[-1].lower().rstrip(".")
            break
    if noun:
        _DEFAULTS[character] = noun
    return noun


def stow_said(s, noun, ask=None):
    """STOW MY <noun> (STOW #id for an id): (True, the answer) unless
    the answer refused it, then (False, the refusal) — for a caller
    that quotes it (#408). A STORE container with no room refuses and
    leaves the item in hand — the game does not fall back — so the item
    then goes into the default container by PUT, said once (#416), and
    the PUT's answer is the one returned. Never a DROP."""
    answer = (ask or act.ask)(s, f"stow {_mine(noun)}")
    if not refused(answer):
        return True, answer
    lowered = str(answer or "").lower()
    if not any(word in lowered for word in STOW_FULL):
        return False, answer
    default = default_container(s, ask)
    if not default:
        return False, answer
    put = (ask or act.ask)(s, f"put {_mine(noun)} in my {default}")
    if refused(put):
        return False, put
    echo = getattr(s, "echo", None)
    if echo:
        echo(f"the {noun} went in the {default} — no room where STOW puts it")
    return True, put


def stow(s, noun, ask=None):
    """stow_said's verdict alone: True unless the STOW (and the fallback
    PUT) was refused."""
    return stow_said(s, noun, ask)[0]


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
    """SHEATHE the weapon where WIELD drew it from — the game remembers
    (the operator, 2026-10-03: "just do sheathe and wield"; a STOW had
    sent the spear to the backpack, "too long to fit", #439). Asked
    where ("Sheathe your ... where?": nothing remembered), into the
    `container` named, else STOW. True unless the answer refused it."""
    ask = ask or act.ask
    answer = ask(s, f"sheathe my {weapon}")
    if any(word in answer.lower() for word in SHEATHE_WHERE) and container:
        answer = ask(s, f"sheathe my {weapon} in my {container}")
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
