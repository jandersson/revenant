"""Keep a Trader's kiosk cast, funded and priced, and resell what it buys:  ;kiosk

    ;kiosk               at the kiosk's room, a pass now and every 5 minutes
    ;kiosk markup=55     the markup it holds, -10 to 80 in steps of 5
    ;kiosk reserve=100   the reserve topped up to this many platinum Kronars ...
    ;kiosk floor=50      ... once it falls under this many
    ;kiosk tap=20        a kind TAPped and resold once the kiosk holds this many platinum of it
    ;kiosk status        the tessera's report, from any room: where, markup, reserve, stored value, time left
    ;kiosk return        (typed while it runs) finish the pass in hand and end; the kiosk stands
    ;stop kiosk          quit at once

A pass
  - Walks to the profile's `kiosk_room` (Grisgonda's, 4652, by default).
  - Casts Prosperity in Absentia at 30 mana with the clear tessera held, and
    again with 2 roisaen left (the wait before that pass shortened to reach
    it), or when the spell is up and its kiosk gone (a logout shatters it);
    finds its own kiosk among the room's by STUDY.
  - PULLs or PUSHes the markup to the target, read back from the answer.
  - STUDYs the other kiosks every 15 minutes and says when one's markup
    moves; the price stays markup= (a markup says nothing of the coin behind it).
  - Reserve under the floor: ;bank keep= the shortfall, then POKE, and POKE again to confirm.
  - A kind over the tap, Trading below lock: Finesse up first, at the mana it
    last took (DISCERN's estimate the first time, 3% lower after each strain),
    RUB to that kind, TAP, then ASK and SELL at the gem shop (pouches) or the
    tannery (bundles); the empty pouch and the rope are kept, the pay banked.
  - STOWs the tessera after every pass and at every end. Never a DROP.

What stops it: no tessera on you (never a cast without it), six kiosks in the
room before a new cast, a cast that fails, its kiosk not found, death.

Modelled on Urbaj's beta kiosk.lic (github.com/urbaj-dr/dr-scripts, branch
kiosk); the seller's side and the kiosk wordings from dr-scripts'
sell-loot.lic. The mechanics are docs/kiosk.md, the wordings client/game/kiosk.py.
"""

import re
from types import SimpleNamespace

from client.game import casting, hands, kiosk, probe, travel
from client.game.act import ask, missing, said, unknown
from client.game.bank import room_currency
from client.game.loop import mindstate
from client.game.mapdb import MapDB
from client.game.money import short
from client.game.profile import load_profile
from client.game.walker import walk

_NOTES = """
Built from the measurements of 2026-10-16 at Grisgonda's (#567, #571;
docs/kiosk.md). kiosk.lic is a one-shot: cast or refresh under a recast
threshold, set the markup when the setting names one, refill under a
minimum, TAP over a minimum, STOW the tessera. ;kiosk runs that pass
every five minutes in the room — every measured sale had the owner
present — and adds the resale, since only the resale teaches Trading:
Finesse before the first ASK (the buyer's figure is fixed per item),
pouches at the gem shop, bundles at the tannery. A resale waits while
Trading is mind-locked: the stored value keeps on the tessera, a locked
skill would waste the lesson. kiosk.lic's REPORT through ASK TESSERA is
not used: the owner's STUDY reads the reserve and the stored value too,
and ;kiosk STUDYs anyway to find its kiosk (ordinals move as kiosks come
and go; a PRIA cast names its own). POKE commits every Kronar carried,
so the top-up goes through ;bank keep=, which deposits the purse first —
a POKE after a ;bank that did not run would have committed it whole.
"""

PLATINUM = 10_000
PASS_SECONDS = 300
# PRIA refreshed with this many roisaen left: a refresh sets the time to
# the new cast's, so what is left is thrown away (8 of 61, 2026-10-17).
RECAST_MINUTES = 2
FINESSE_MINUTES = 5  # Finesse recast before a sale with fewer left
STEPS = 20  # PULLs or PUSHes in one setting; -10 to 80 is 18
MARKET_MINUTES = 15  # another's kiosk STUDYed again after this long
ROPE = "bundling rope"
_TANNER = re.compile(r"\btanner (\w+)")  # "the tanner Falken", as ;skins reads it


def parse_args(words):
    options = {
        "status": False,
        "markup": 55,
        "reserve": 100 * PLATINUM,
        "floor": 50 * PLATINUM,
        "tap": 20 * PLATINUM,
    }
    for word in words or []:
        key, sep, value = str(word).lower().partition("=")
        if key == "status" and not sep:
            options["status"] = True
        elif sep and key == "markup" and re.fullmatch(r"-?\d+", value):
            options["markup"] = int(value)
        elif sep and key in ("reserve", "floor", "tap") and value.isdigit():
            options[key] = int(value) * PLATINUM
    options["markup"] = kiosk.markup_target(options["markup"])
    return options


def up(s, spell, minutes=-1):
    """True when the Spells window lists `spell` with more than `minutes`
    roisaen left (a line with no count: up); listed at all by default."""
    for name, left in (getattr(s.state, "active_spells", None) or {}).items():
        if name.lower() == spell.lower():
            return left is None or left > minutes
    return False


def next_wait(s):
    """Seconds to the next pass: PASS_SECONDS, or fewer so that the pass
    that refreshes PRIA comes with RECAST_MINUTES left, not a pass early
    (a roisaen is a minute)."""
    for name, left in (getattr(s.state, "active_spells", None) or {}).items():
        if name.lower() == kiosk.SPELL.lower() and left is not None:
            return max(60, min(PASS_SECONDS, (left - RECAST_MINUTES) * 60))
    return PASS_SECONDS


def time_left(s):
    for name, left in (getattr(s.state, "active_spells", None) or {}).items():
        if name.lower() == kiosk.SPELL.lower():
            return f"{left} roisaen left" if left is not None else "up"
    return f"{kiosk.SPELL} is not up"


def take_tessera(s):
    """The clear tessera in a hand, a hand freed for it: True when it is."""
    if hands.holding(s, "tessera"):
        return True
    hands.free_one(s, keep=("tessera",), ask=ask)
    return not missing(ask(s, f"get my {kiosk.TESSERA}"))


def stow_tessera(s):
    if hands.holding(s, "tessera"):
        hands.stow(s, "tessera", ask=ask)


def cast_kiosk(s):
    """PRIA cast with the tessera held: (outcome, the kiosk's name or None)."""
    seen = []

    def recording(s, command):
        answer = ask(s, command)
        seen.append(answer)
        return answer

    def report(what, answer):
        if not kiosk.cast_name(answer):  # the kiosk's growing is no CAST wording
            unknown(s, "kiosk", f"{kiosk.SPELL}'s {what}", answer)

    outcome = casting.cast_once(
        s, kiosk.SPELL_ABBREV, kiosk.MANA, casting.CastState(), recording, report
    )
    return outcome, next((n for n in map(kiosk.cast_name, seen) if n), None)


def grow(s, st, standing):
    """PRIA cast, a new kiosk (not `standing`) only under six in the room:
    why it failed, or None. The kiosk's name is kept."""
    objs = getattr(s.state, "room_objs", "")
    if not standing and len(kiosk.listing(objs)) >= kiosk.MAX_KIOSKS:
        return f"{kiosk.MAX_KIOSKS} kiosks already stand here"
    outcome, name = cast_kiosk(s)
    if outcome not in ("ok", "strained"):
        return f"{kiosk.SPELL} did not cast ({outcome})"
    st.name = name or st.name
    return None


def find(s, st):
    """STUDY the room's kiosks, the one last known first, until one answers
    to its owner: that reading, or None. The target and name are kept."""
    entries = kiosks_here(s)
    entries.sort(key=lambda entry: (entry[1] != st.name, entry[0] != st.target))
    for target, name, key in entries:
        reading = kiosk.read_study(ask(s, f"study {target}"))
        if reading and reading["owner"]:
            st.target, st.name = target, name
            return reading
        if reading:
            note(s, st, key, name, reading)
    return None


def kiosks_here(s):
    """[(target, name, key)] for each kiosk the room lists, the key its
    name and its place among kiosks of that look: two euhedral are two."""
    seen, out = {}, []
    for target, name in kiosk.listing(getattr(s.state, "room_objs", "")):
        seen[name] = seen.get(name, 0) + 1
        out.append((target, name, f"{name} #{seen[name]}"))
    return out


def note(s, st, key, name, reading):
    """Another's kiosk read: kept, its markup said when it is new or moved."""
    seen = st.market.get(key)
    st.market[key] = {"markup": reading["markup"], "at": probe.clock()}
    if not seen or seen["markup"] != reading["markup"]:
        who = f"{reading['trader']}'s kiosk" if reading.get("trader") else f"the {name}"
        s.echo(f"kiosk: {who} at {reading['markup']}%")


def market(s, st):
    """STUDY each other kiosk here not read for MARKET_MINUTES, its markup
    said by note() when it moves. The price stays markup=: a markup says
    nothing of the coin behind it (ours sold out at 80% in 26 minutes)."""
    for target, name, key in kiosks_here(s):
        seen = st.market.get(key)
        if target == st.target or (
            seen and probe.clock() - seen["at"] < MARKET_MINUTES * 60
        ):
            continue
        reading = kiosk.read_study(ask(s, f"study {target}"))
        if reading and not reading["owner"]:
            note(s, st, key, name, reading)


def set_markup(s, st, markup, target):
    """PULL or PUSH until the kiosk says `target`: True when it does."""
    for _ in range(STEPS):
        if markup is None or markup == target:
            return markup == target
        verb = "pull" if markup < target else "push"
        answer = ask(s, f"{verb} {st.target}")
        markup = kiosk.markup_of(answer)
        if markup is None and kiosk.NOT_OWNER not in answer.lower():
            unknown(s, "kiosk", verb.upper(), answer)
    return markup == target


def run_bank(s, words):
    """;bank with `words`, waited for: False, said, when it could not start."""
    if not s.run("bank", list(words)):
        s.echo("kiosk: could not start ;bank — no top-up")
        return False
    try:
        while s.is_running("bank"):
            s.sleep(1)
    except BaseException:
        s.kill("bank")  # ;stop kiosk takes the ;bank with it
        raise
    return True


def fund(s, st, mapdb, walk_fn, room, copper):
    """`copper` Kronars into the reserve: ;bank leaves them in the purse
    (POKE commits every Kronar carried), then POKE asks and POKE again
    commits. True when the kiosk took them."""
    stow_tessera(s)
    here = travel.here(s, mapdb)
    coin = "keep" if room_currency(mapdb, here).lower() == "kronars" else "kronars"
    if not run_bank(s, [f"{coin}={copper}"]):
        return False
    if not travel.go(s, room, "the kiosk's room", db=mapdb, walk=walk_fn):
        return False
    if not take_tessera(s) or find(s, st) is None:
        return False
    first = ask(s, f"poke {st.target}")
    if kiosk.POKE_ASKS not in first.lower():
        unknown(s, "kiosk", "POKE", first)
        return False
    second = ask(s, f"poke {st.target}")
    if kiosk.POKED not in second.lower():
        unknown(s, "kiosk", "POKE", second)
        return False
    return True


def finesse(s):
    """Finesse up before a sale, FINESSE_MINUTES to spare, at the most mana
    it holds (its power is its mana, #573): True when it is."""
    if up(s, kiosk.FINESSE, FINESSE_MINUTES):
        return True
    outcome, mana = casting.held_cast(
        s,
        kiosk.FINESSE,
        kiosk.FINESSE_ABBREV,
        casting.CastState(),
        ask,
        lambda what, answer: unknown(s, "kiosk", f"Finesse's {what}", answer),
    )
    if outcome == "ok":
        return True
    s.echo(f"kiosk: Finesse did not cast ({outcome} at {mana}) — no resale this pass")
    return False


def buyer(s, kind):
    """Who the ASK goes to: the appraiser at a gem shop, the tanner by
    name at a tannery; None when the room lists neither."""
    objs = str(getattr(s.state, "room_objs", "") or "")
    if kind == "pouch":
        return "appraiser" if "appraiser" in objs.lower() else None
    tanner = _TANNER.search(objs)
    return tanner.group(1).lower() if tanner else None


def resell(s, st, mapdb, walk_fn, room, kind, dispense, profile):
    """TAP `kind`, Finesse up first, and sell it, back at the kiosk's room
    after: True once the TAP went out, False, said, when it did not."""
    if not finesse(s) or not take_tessera(s):
        return False
    for _ in range(2):  # RUB toggles pouches and bundles
        if dispense == kind:
            break
        dispense = kiosk.rub_mode(ask(s, f"rub {st.target}"))
    if dispense != kind:
        s.echo(f"kiosk: the kiosk would not switch to {kind} sales")
        return False
    answer = ask(s, f"tap {st.target}")
    if kiosk.tapped(answer) != kind:
        unknown(s, "kiosk", "TAP", answer)
        return False
    stow_tessera(s)
    if sell(s, mapdb, walk_fn, kind, profile) is not None:
        # The pay banked before the wait by the kiosk: a pickpocket's mark.
        run_bank(s, [])
    travel.go(s, room, "the kiosk's room", db=mapdb, walk=walk_fn)
    return True


def sell(s, mapdb, walk_fn, kind, profile):
    """The TAPped item sold at the gem shop or the tannery, ASKed first:
    the copper paid, or None, said. The empty pouch and the rope kept."""
    shop = "gemshop" if kind == "pouch" else "tannery"
    if not travel.go(
        s, mapdb.rooms_tagged(shop), f"the {shop}", db=mapdb, walk=walk_fn
    ):
        s.echo(f"kiosk: could not reach a {shop} — the {kind} stays with you")
        return None
    if not hands.holding(s, kind):  # never a SELL MY POUCH at a worn gem pouch
        s.echo(f"kiosk: no {kind} in hand to sell")
        return None
    npc = buyer(s, kind)
    offer = kiosk.offered(ask(s, f"ask {npc} to appraise my {kind}")) if npc else None
    answer = ask(s, f"sell my {kind}")
    copper = kiosk.paid(answer)
    if copper is None:
        s.echo(f"kiosk: the {kind} did not sell — {said(answer)}")
        return None
    quoted = f" (quoted {short(offer)})" if offer and offer != copper else ""
    s.echo(f"kiosk: sold the {kind} for {short(copper)}{quoted}")
    if kind == "pouch":
        hands.stow(s, "pouch", ask=ask)  # the empty pouch, a spare
    else:
        container = profile.get("loot_container")
        ask(s, f"put my {ROPE} in my {container}" if container else f"stow my {ROPE}")
    return copper


def status(s):
    """The tessera's report in a line, read from wherever the character
    stands; the tessera put back where it was."""
    held = hands.holding(s, "tessera")
    if not take_tessera(s):
        return "kiosk: no clear tessera on you"
    answer = ask(s, kiosk.REPORT)
    if not held:
        stow_tessera(s)
    reading = kiosk.read_report(answer)
    if reading is None:
        return f"kiosk: no report — {said(answer)}; {time_left(s)}"
    return (
        f"kiosk: at [{reading['room']}] — markup {reading['markup']}%, reserve "
        f"{short(reading['reserve'])}, stored {short(reading['pouch'])} in pouches "
        f"and {short(reading['bundle'])} in bundles, {time_left(s)}"
    )


def describe(s, st, reading):
    return (
        f"kiosk: the {st.target} — markup {reading['markup']}%, reserve "
        f"{short(reading['reserve'])}, stored {short(reading['pouch'])} in pouches and "
        f"{short(reading['bundle'])} in bundles, {time_left(s)}"
    )


def one_pass(s, st, options, profile, mapdb, walk_fn, room):
    """Cast, find, price, fund and resell once: why the run must end, or None."""
    if s.dead:
        return "you are dead"
    if not travel.go(s, room, "the kiosk's room", db=mapdb, walk=walk_fn):
        return "could not reach the kiosk's room"
    hands.clear(s, profile, ask=ask, keep=("tessera",))
    if not take_tessera(s):
        return "no clear tessera on you — never a cast without it"
    cast = not up(s, kiosk.SPELL, RECAST_MINUTES)
    if cast and (why := grow(s, st, standing=up(s, kiosk.SPELL))):
        return why
    reading = find(s, st)
    if reading is None and not cast and up(s, kiosk.SPELL):
        # A logout shatters the kiosk and leaves the spell up (2026-10-16):
        # the cast grows another, the ledger intact, the markup at 0%.
        if why := grow(s, st, standing=False):
            return why
        reading = find(s, st)
    if reading is None:
        return "found no kiosk of yours here"
    if reading["markup"] != options["markup"]:
        if set_markup(s, st, reading["markup"], options["markup"]):
            reading["markup"] = options["markup"]
        else:
            s.echo(f"kiosk: the markup stays at {reading['markup']}%")
    need = kiosk.topup(reading["reserve"], options["floor"], options["reserve"])
    if need and not st.unfunded:
        if fund(s, st, mapdb, walk_fn, room, need):
            reading["reserve"] += need
            s.echo(f"kiosk: put {short(need)} into the reserve")
        else:
            st.unfunded = True
            s.echo("kiosk: the reserve was not topped up — no more top-ups this run")
    locked = (mindstate(s, "Trading") or 0) >= casting.MIND_LOCK
    dispense = reading["dispense"]
    for kind in ("pouch", "bundle"):
        if kiosk.due(reading, kind, options["tap"]) and not locked:
            if resell(s, st, mapdb, walk_fn, room, kind, dispense, profile):
                dispense = kind
                reading[kind] = max(0, reading[kind] - kiosk.TAP_MAX)
    stow_tessera(s)
    market(s, st)
    line = describe(s, st, reading)
    if line.rsplit(",", 1)[0] != (st.said or "").rsplit(",", 1)[0]:
        s.echo(line)  # said when something but the time left moved
    st.said = line
    return None


def idle(s, st, seconds):
    """The wait for the next pass, in one-second slices: False once
    return is typed or the character died; a typed status is answered."""
    for _ in range(int(seconds)):
        while (line := s.command(timeout=0)) is not None:
            if "return" in line.lower():
                return False
            if "status" in line.lower():
                s.echo(st.said or "kiosk: no reading yet")
        if s.dead:
            return False
        s.sleep(1)
    return True


def run(s, options, mapdb, walk_fn=walk, profile=None):
    if profile is None:
        profile = load_profile(getattr(s.state, "name", None) or "")
    st = SimpleNamespace(target=None, name=None, said=None, unfunded=False, market={})
    if options["status"]:
        s.echo(status(s))
        return None
    room = profile.get("kiosk_room") or kiosk.ROOM
    s.echo(f"kiosk: a pass every {PASS_SECONDS // 60} minutes — ;kiosk return ends it")
    try:
        while True:
            why = one_pass(s, st, options, profile, mapdb, walk_fn, room)
            if why:
                s.echo(f"kiosk: {why} — stopping")
                return why
            if not idle(s, st, next_wait(s)):
                s.echo("kiosk: done — the kiosk stands")
                return None
    finally:
        hands.at_end(s, ("tessera", "pouch", "bundle", "rope"))


def main(s):
    run(s, parse_args(s.args), MapDB.load())
