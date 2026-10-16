"""How ;kiosk keeps a Trader's kiosk — these tests are the manual (#571).
A pass walks to the kiosk's room, casts Prosperity in Absentia with the
tessera held when it is down or nearly so, finds its kiosk by STUDY,
sets the markup, tops the reserve up through ;bank and POKE, and resells
what the kiosk bought with Finesse up. The wordings were captured at
Grisgonda's on 2026-10-16 (#567); names are the synthetic cast's."""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.game import casting, kiosk
from client.game.mapdb import MapDB
from client.game.money import phrase

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "kiosk_script", REPO / "scripts/kiosk.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

PLAT = 10_000

# --- the captured wordings ---

ROOM_OBJS = (
    "You also see a heptagonally symmetrical crystalline kiosk, a poorly made pine "
    "strongbox, an iridescent crystal kiosk traced in softly lit starburst etchings, "
    "a cracked deobar chest, a euhedral crystalline kiosk, some display cases with "
    "several things on it, a Dwarven appraiser and a silver bucket."
)
GREW = (
    "Your tessera grows cold, flickering in a complex undulating pattern, and extends "
    "a pair of opposingly oriented posts which shine hair-thin lances of green-orange "
    "light at an empty area of space nearby, growing a frosty crystal of Iridius which "
    "begins to expand.  The tessera continues to paint the crystal with zigzagging "
    "light, guiding its growth, and with the sound of shattering glass and a hiss of "
    "displaced air, a heptagonally symmetrical crystalline kiosk unfolds from "
    "nothingness.\n\nWith the construction complete, the tessera chirrups in a series "
    "of tones and snaps back to its normal cube-shaped configuration.  The kiosk "
    "ripples slightly, now receptive to commerce."
)
# A bystander's refresh, 2026-10-16; the caster's own is kiosk.lic's "You gesture at".
REFRESHED = (
    "You gesture at a euhedral crystalline kiosk, which responds by briefly "
    "undulating with green-orange hues."
)
SENSED = (
    "You sense your Properity in Abstentia spell within a heptagonally symmetrical "
    "crystalline kiosk, which will last for about fifteen roisaen.  It is deployed at "
    "[Grisgonda's, Appraisal Room], and has coin reserves."
)
VERBS = """As you examine your kiosk, a silvery-voiced message ringing of glass and order echoes in your mind.  As the owner of this arbitration mechanism, the following interactions are available to you:

   PULL - Increase the markup in 5% increments, to a maximum of 80%.
   PUSH - Decrease the markup in 5% increments, to a minimum of -10%.
   POKE - Commit all available Kronars to the kiosk's purchasing reserves for acquiring pouches and
          bundles from interested parties.  Up to 1,000 platinum Kronars may be held in reserve.
  TOUCH - Reclaim all Kronars currently held in the kiosk's purchasing reserves.
    RUB - Toggle between held pouch and bundle assets.
    TAP - Convert up to 500 platinum Kronars of stored asset value into a tied gem pouch or bundle.

You note that your kiosk is currently configured to dispense tied gem pouches.
"""
NEW_STUDY = (
    VERBS
    + """
During this kiosk's trading session, it has purchased the following:
  No Kronars in pouches.
  No Kronars in bundles.
  The markup is set to 0%.

Finally, your kiosk's current reserves are:
  It currently holds no funds for purchases.
  No Kronars in pouches.
  No Kronars in bundles.

Flowing like water, the kiosk returns to its normal form.
Roundtime: 5 sec."""
)
BUSY_STUDY = (
    VERBS
    + """
During this kiosk's trading session, it has purchased the following:
  78 platinum, 6 gold, 9 silver and 1 bronze Kronars in pouches.
  21 platinum, 3 gold, 7 bronze, and 2 copper Kronars in bundles.
  The markup is set to 80%.

Finally, your kiosk's current reserves are:
  It holds 20 platinum, 1 bronze, and 8 copper Kronars in reserve for purchases.
  43 platinum, 7 gold, 1 silver, 7 bronze, and 2 copper Kronars in pouches.
  11 platinum, 8 gold, 3 silver, 7 bronze, and 3 copper Kronars in bundles.

Flowing like water, the kiosk returns to its normal form.
Roundtime: 5 sec."""
)
NOT_OWNER = (
    "As you are not the owner of a euhedral crystalline kiosk, it rearranges slightly "
    "and displays the following information:\n"
    "  The markup is set to 55%.\n"
    "  The kiosk is actively buying pouches and bundles if it has enough coin in reserve.\n"
    "  Per guild privilege, the kiosk also indicates that its owner is Sable.\n"
    "Roundtime: 5 sec."
)
PULLED = (
    "You pull the top of the crystalline kiosk, and it ripples like water, its surface "
    "coalescing into ordered crystalline facets indicating the markup it will pay is "
    "set to {}%."
)
POKE_ASKS = (
    "The tessera swiftly rearranges in a series of involutions, and a silvery-voiced "
    'message ringing of glass and order echoes in your mind, "Purchasing reserves are '
    "limited to 1,000 platinum Kronars.  If you wish to commit an additional 100 "
    "platinum Kronars toward that limit, repeat the request to confirm your "
    'intention."\n[Repeat the command within 10 seconds to proceed.]'
)
POKED = (
    "A heptagonally symmetrical crystalline kiosk ripples like water, and the surface "
    "spirals open, revealing an empty interior chamber.  You drop some Kronars into "
    "the crystalline kiosk, which chimes and closes seamlessly.  After a brief moment, "
    "the kiosk pulses with soft light and chimes merrily.\nRoundtime: 5 sec."
)
RUBBED = (
    "You rub the crystalline kiosk, and it shifts along multiple axes, displaying a "
    "pile of pelts, horns, and bones.  It is now set to pay out {} sales."
)
TAPPED = (
    "A heptagonally symmetrical crystalline kiosk ripples like water, and the surface "
    "spirals open, revealing a crystalline {} dusted in frost, which you remove.  After "
    "a moment, the kiosk chimes and closes seamlessly.  Your tessera vibrates, and a "
    'silvery-voiced message ringing of glass and order echoes in your mind, "The '
    "disbursement of {} liabilities has been processed and recorded to your "
    'tessera-ledger."\nRoundtime: 6 sec.'
)
APPRAISED = (
    "You ask the Dwarf to appraise a crystalline gem pouch.\n"
    "The Dwarf examines the contents of the gem pouch carefully, then whispers, "
    '"I\'ll pay 723250 Kronars for it."'
)
APPRAISED_AGAIN = (
    'The Dwarf glares at you and says, "723250 Kronars, take it or leave it!"'
)
SOLD_POUCH = (
    "The Dwarven appraiser scrutinizes the contents of the gem pouch carefully, then "
    "hands you 723250 Kronars."
)
TANNER_QUOTE = (
    "You ask the tanner Falken to appraise a crystalline tight bundle.\n"
    "The tanner Falken looks the tight bundle over carefully, then whispers, "
    '"I can give 245832 Kronars for it."'
)
TANNER_AGAIN = (
    'The tanner Falken shakes his head and says, "245832 Kronars is what its worth, '
    "245832 is what I'll take.\""
)
SOLD_BUNDLE = (
    "You ask the tanner Falken to buy a crystalline tight bundle.\n"
    "The tanner Falken ponders over the bundle for a while, then hands you 245832 "
    'Kronars.\nTanner Falken says, "And there\'s your rope back again."'
)
FINESSE_CAST = (
    "You gesture.\nSharpened beneath the spell pattern's lens, your proprioception and "
    "social instincts burgeon in phrenic harmony."
)
# DISCERN FINESSE and the strained PREPARE, a circle-90 Trader (#570).
DISCERN_FINESSE = (
    "It requires the Augmentation skill to cast effectively.\n"
    "The spell requires at minimum 5 mana streams and you think you can reinforce "
    "it with 75 more, for a total of 80 streams."
)
STRAINED = (
    "You trace an angular sigil in the air, shaping the pattern of the Finesse "
    "spell.\nYou feel intense strain as you try to manipulate the mana streams to "
    "form this pattern, and you are not certain that you will have enough mental "
    "stamina to complete it."
)
RELEASED = "You let your concentration lapse and feel the spell's energies dissipate."
# ASK MY TESSERA ABOUT REPORT, the same in the kiosk's room and the shop
# outside it (2026-10-17).
REPORT = (
    "You send your clear tessera a wordless thought of acquiescence.\n"
    "Your head fills with the psychic backlash of the Negotiants' chatter, \"... "
    'TRANSACTIONAL ANALYSIS ALIGNS WITH INCENTIVE-PERSUASION...", cut short when '
    "the tessera swiftly rearranges in a series of involutions, and a silvery-voiced "
    'message ringing of glass and order echoes in your mind, "Analysis complete.  '
    'Audit-abstraction follows."\n'
    "A flurry of glimmering geometries and abstract ratios flit across your field of "
    "view, describing key sales data:\n"
    "The crystalline kiosk is presently located at [Grisgonda's, Appraisal Room].\n"
    "During this kiosk's trading session, it has purchased the following:\n"
    "  32 platinum, 3 gold, 8 silver and 8 bronze Kronars in pouches.\n"
    "  42 platinum, 7 gold, and 8 copper Kronars in bundles.\n"
    "  The markup is set to 60%.\n"
    "Finally, your kiosk's current asset holdings are:\n"
    "  It has a total of 22 platinum, 9 gold, 8 bronze, and 6 copper Kronars on hand "
    "for purchases.\n"
    "  40 platinum, 1 gold, 5 silver, 8 bronze, and 9 copper Kronars in pouches.\n"
    "  26 platinum, 5 gold, 8 silver, 1 bronze, and 3 copper Kronars in bundles.\n"
    "The floating data fades with a friendly chime, leaving you blinking away a brief "
    "visual afterglow.\nRoundtime: 6 sec."
)


# --- the model ---


def test_the_room_listing_gives_each_kiosk_its_ordinal_and_name():
    assert kiosk.listing(ROOM_OBJS) == [
        ("kiosk", "heptagonally symmetrical crystalline kiosk"),
        (
            "second kiosk",
            "iridescent crystal kiosk traced in softly lit starburst etchings",
        ),
        ("third kiosk", "euhedral crystalline kiosk"),
    ]


def test_an_and_inside_a_kiosks_name_stays_in_it():
    objs = "You also see a spindly and acicular crystalline kiosk and a ruined caravan."
    assert kiosk.listing(objs) == [("kiosk", "spindly and acicular crystalline kiosk")]


def test_a_plinth_counts_on_its_own_noun():
    objs = (
        "You also see a euhedral crystalline kiosk and a luminescent Iridius crystal "
        "plinth protected by a faceted glass-like dragon."
    )
    assert [target for target, _ in kiosk.listing(objs)] == ["kiosk", "plinth"]


def test_the_cast_the_refresh_and_power_name_the_kiosk():
    assert kiosk.cast_name(GREW) == "heptagonally symmetrical crystalline kiosk"
    assert kiosk.cast_name(REFRESHED) == "euhedral crystalline kiosk"
    assert kiosk.cast_name(SENSED) == "heptagonally symmetrical crystalline kiosk"
    assert kiosk.cast_name("You gesture.") is None


def test_the_owners_study_of_a_new_kiosk_reads_empty_at_zero():
    assert kiosk.read_study(NEW_STUDY) == {
        "owner": True,
        "markup": 0,
        "reserve": 0,
        "pouch": 0,
        "bundle": 0,
        "dispense": "pouch",
    }


def test_the_owners_study_reads_what_it_holds_now_not_the_sessions_purchases():
    reading = kiosk.read_study(BUSY_STUDY)
    assert reading["markup"] == 80
    assert reading["reserve"] == 20 * PLAT + 18
    assert reading["pouch"] == 43 * PLAT + 7_000 + 100 + 72
    assert reading["bundle"] == 11 * PLAT + 8_000 + 300 + 73


def test_another_traders_kiosk_shows_its_markup_and_no_reserve():
    assert kiosk.read_study(NOT_OWNER) == {
        "owner": False,
        "markup": 55,
        "trader": "Sable",
    }
    assert kiosk.read_study("You see nothing unusual.") is None


def test_pull_and_push_answers_read_the_markup():
    assert kiosk.markup_of(PULLED.format(55)) == 55
    assert kiosk.markup_of(PULLED.format(-10)) == -10


def test_a_wanted_markup_lands_on_the_kiosks_steps():
    assert kiosk.markup_target(57) == 55
    assert kiosk.markup_target(95) == 80
    assert kiosk.markup_target(-20) == -10


def test_a_top_up_fills_to_the_target_only_under_the_floor():
    assert kiosk.topup(20 * PLAT, 50 * PLAT, 100 * PLAT) == 80 * PLAT
    assert kiosk.topup(60 * PLAT, 50 * PLAT, 100 * PLAT) == 0


def test_tap_rub_and_the_buyers_figures_are_read():
    assert kiosk.tapped(TAPPED.format("pouch", "pouch")) == "pouch"
    assert kiosk.tapped(TAPPED.format("bundle", "bundle")) == "bundle"
    assert kiosk.rub_mode(RUBBED.format("bundle")) == "bundle"
    assert kiosk.offered(APPRAISED) == 723250
    assert kiosk.offered(APPRAISED_AGAIN) == 723250
    assert kiosk.offered(TANNER_QUOTE) == 245832
    assert kiosk.offered(TANNER_AGAIN) == 245832
    assert kiosk.paid(SOLD_POUCH) == 723250
    assert kiosk.paid(SOLD_BUNDLE) == 245832


# --- the script ---

MAP = MapDB(
    [
        {
            "id": 4652,
            "uid": [1],
            "title": ["[Grisgonda's, Appraisal Room]"],
            "tags": ["gemshop"],
            "wayto": {},
        },
        {
            "id": 8266,
            "uid": [2],
            "title": ["[Falken's Tannery, Workshop]"],
            "tags": ["tannery"],
            "wayto": {},
        },
    ]
)
TANNERY_OBJS = "You also see the tanner Falken and a counter."
MISSING = "What were you referring to?"


@pytest.fixture(autouse=True)
def _no_spell_waits(monkeypatch):
    # A fake counts no prompts: the pattern's eight seconds and the CAST's
    # second window would be waited out in real time.
    monkeypatch.setattr(casting, "PREPARE_SECONDS", 0)
    monkeypatch.setattr(casting, "CAST_TAIL_SECONDS", 0.01)


def ours(name="euhedral crystalline kiosk", **fields):
    """Our kiosk as the fake keeps it: priced, funded above the floor, empty."""
    return {
        "name": name,
        "markup": 55,
        "reserve": 60 * PLAT,
        "pouch": 0,
        "bundle": 0,
        "dispense": "pouch",
        **fields,
    }


class Room:
    """Grisgonda's with kiosks in it — ours among them once cast, listed
    after `before` and ahead of `after` — and a handle that answers as
    the game did. The run ends at its first wait: "return" is typed."""

    def __init__(
        self,
        before=(),
        mine=None,
        after=(),
        spells=None,
        tessera=True,
        trading=10,
        ledger=None,
        grows="heptagonally symmetrical crystalline kiosk",
        finesse_max=72,
    ):
        self.before, self.after = list(before), list(after)  # someone else's
        self.mine = mine
        # What the tessera keeps for a kiosk a cast grows, and its look.
        self.ledger = ledger or ours(reserve=0)
        self.grows = grows
        self.finesse_max = (
            finesse_max  # the most Finesse mana that forms without strain
        )
        self.tessera = tessera
        self.sent, self.echoed, self.started, self.pending = [], [], [], []
        self.poke_asked = False
        self.carried = 0  # the Kronars ;bank left in the purse
        self.can_bank = True
        self.dead = False
        self.args = []
        self.typed = ["return"]
        self.state = SimpleNamespace(
            name="Lanival",
            room_uid=1,
            room_objs="",
            active_spells=dict(spells or {}),
            left_hand=None,
            right_hand=None,
            experience={"Trading": {"rank": 767, "percent": 29, "mindstate": trading}},
        )
        self.list_room()

    def list_room(self):
        if self.state.room_uid != 1:
            self.state.room_objs = TANNERY_OBJS
            return
        names = self.before + ([self.mine["name"]] if self.mine else []) + self.after
        listed = ", ".join(f"a {name}" for name in names)
        self.state.room_objs = f"You also see {listed} and a Dwarven appraiser."

    def holds(self, noun):
        return any(
            (getattr(self.state, f"{side}_hand") or {}).get("noun") == noun
            for side in ("left", "right")
        )

    def hold(self, noun, name=None):
        """Into the free hand, the right first, as the game fills them."""
        side = "left" if self.state.right_hand else "right"
        setattr(self.state, f"{side}_hand", {"noun": noun, "name": name or noun})

    def let_go(self, noun):
        for side in ("left", "right"):
            if (getattr(self.state, f"{side}_hand") or {}).get("noun") == noun:
                setattr(self.state, f"{side}_hand", None)

    def kiosk_at(self, target):
        """Ours (the dict) or another's name, as the target names it now."""
        for listed, name in kiosk.listing(self.state.room_objs):
            if listed == target:
                return self.mine if self.mine and name == self.mine["name"] else name
        return None

    def study(self):
        mine = self.mine

        def held(kind, plural):
            if not mine[kind]:
                return f"No Kronars in {plural}."
            return f"{phrase(mine[kind], 'Kronars')} in {plural}."

        reserve = (
            f"It holds {phrase(mine['reserve'], 'Kronars')} in reserve for purchases."
            if mine["reserve"]
            else "It currently holds no funds for purchases."
        )
        verbs = VERBS
        if mine["dispense"] == "bundle":
            verbs = verbs.replace("tied gem pouches", "tied bundles")
        return (
            f"{verbs}\nDuring this kiosk's trading session, it has purchased the "
            f"following:\n  No Kronars in pouches.\n  No Kronars in bundles.\n"
            f"  The markup is set to {mine['markup']}%.\n\n"
            f"Finally, your kiosk's current reserves are:\n  {reserve}\n"
            f"  {held('pouch', 'pouches')}\n  {held('bundle', 'bundles')}\n\n"
            "Roundtime: 5 sec."
        )

    def cast(self):
        self.state.active_spells[kiosk.SPELL] = 61
        if self.mine:
            return (
                f"You gesture at a {self.mine['name']}, which responds by briefly "
                "undulating with green-orange hues."
            )
        self.mine = {**self.ledger, "name": self.grows, "markup": 0}
        self.after, self.before = self.before + self.after, []  # a new one lists first
        self.list_room()
        return GREW.replace("heptagonally symmetrical crystalline kiosk", self.grows)

    def answer(self, command):
        verb, _, rest = command.partition(" ")
        if command == "get my clear tessera":
            if not self.tessera:
                return MISSING
            self.hold("tessera", "clear tessera")
            return "You get a clear tessera from inside your backpack."
        if verb == "stow" or command.startswith("put my bundling rope"):
            noun = "rope" if verb == "put" else command.split()[-1]
            self.let_go(noun)
            return "You put it in your backpack."
        if command == kiosk.REPORT:
            return REPORT if self.holds("tessera") else MISSING
        if command.lower() == "discern finesse":
            return DISCERN_FINESSE
        if command == "release":
            return RELEASED
        if (
            command.startswith("prepare fin ")
            and int(command.split()[-1]) > self.finesse_max
        ):
            return STRAINED
        if verb == "prepare":
            return (
                "You raise your arms skyward, chanting the equation of the spell.\n"
                "You feel fully prepared to cast your spell."
            )
        if verb == "cast" and self.sent[-2].startswith("prepare fin"):
            self.state.active_spells["Finesse"] = 33
            return FINESSE_CAST
        if verb == "cast":
            return self.cast()
        if verb in ("study", "pull", "push", "poke", "rub", "tap"):
            target = self.kiosk_at(rest)
            if not isinstance(target, dict):
                return NOT_OWNER.replace("euhedral crystalline kiosk", str(target))
            if verb == "study":
                return self.study()
            if verb in ("pull", "push"):
                target["markup"] += 5 if verb == "pull" else -5
                return PULLED.format(target["markup"])
            if verb == "poke":
                self.poke_asked = not self.poke_asked
                if self.poke_asked:
                    return POKE_ASKS
                target["reserve"] += self.carried
                self.carried = 0
                return POKED
            if verb == "rub":
                target["dispense"] = (
                    "bundle" if target["dispense"] == "pouch" else "pouch"
                )
                return RUBBED.format(target["dispense"])
            kind = target["dispense"]
            target[kind] = 0
            self.hold(kind, f"crystalline {kind}")
            return TAPPED.format(kind, kind)
        if command == "ask appraiser to appraise my pouch":
            return APPRAISED
        if command == "ask falken to appraise my bundle":
            return TANNER_QUOTE
        if command == "sell my pouch" and self.holds("pouch"):
            return SOLD_POUCH  # the empty pouch stays in hand
        if command == "sell my bundle" and self.holds("bundle"):
            self.let_go("bundle")
            self.hold("rope", "bundling rope")
            return SOLD_BUNDLE
        return MISSING

    # --- the handle ---

    def put(self, command):
        self.sent.append(command)
        self.pending = [line + "\n" for line in self.answer(command).splitlines()]

    def get(self, timeout=None, streams=("",)):
        if timeout == 0 or not self.pending:
            return None
        return self.pending.pop(0)

    def echo(self, text):
        self.echoed.append(text)

    def command(self, timeout=None):
        return self.typed.pop(0) if self.typed else None

    def run(self, name, args=()):
        if not self.can_bank:
            return False
        self.started.append((name, list(args)))
        # ;bank keep=N leaves N carried; a plain ;bank deposits it all.
        self.carried = int(args[0].split("=")[1]) if args else 0
        return True

    def is_running(self, name):
        return False

    def kill(self, name):
        pass

    def sleep(self, seconds):
        pass

    def waitrt(self):
        pass


def walk(s, db, goals, describe="", avoid=()):
    s.state.room_uid = db.rooms[min(goals)]["uid"][0]
    s.list_room()
    return True


PROFILE = {"buffs": ["Finesse:72"], "loot_container": "sack"}


def run(room, *words):
    options = script.parse_args(list(words))
    return script.run(room, options, MAP, walk_fn=walk, profile=PROFILE)


def sent(room, verb):
    return [command for command in room.sent if command.split()[0] == verb]


def test_a_first_pass_casts_with_the_tessera_held_then_prices_and_funds_the_kiosk():
    room = Room(after=["euhedral crystalline kiosk"])
    assert run(room) is None
    prepare = room.sent.index("prepare pria 30")
    assert room.sent.index("get my clear tessera") < prepare
    assert room.sent[prepare + 1] == "cast"
    # The new kiosk lists first and its cast named it: one STUDY finds it,
    # one more after the ;bank trip, since kiosks come and go meanwhile,
    # and the other's kiosk is read for its markup.
    assert sent(room, "study") == ["study kiosk", "study kiosk", "study second kiosk"]
    assert sent(room, "pull") == ["pull kiosk"] * 11  # 0% up to 55%
    assert room.mine["markup"] == 55
    # Empty, so under the floor: ;bank leaves the shortfall, POKE asks, POKE commits.
    assert room.started == [("bank", ["keep=1000000"])]
    assert sent(room, "poke") == ["poke kiosk", "poke kiosk"]
    assert room.mine["reserve"] == 100 * PLAT
    assert [c for c in room.sent if "tessera" in c][-1] == "stow my tessera"
    assert not room.holds("tessera")


def test_its_own_kiosk_is_found_by_study_among_the_others():
    room = Room(
        before=["euhedral crystalline kiosk"],
        mine=ours("jaggedly dendritic crystalline kiosk"),
        spells={kiosk.SPELL: 30},
    )
    run(room)
    assert sent(room, "prepare") == []  # 30 roisaen left
    assert sent(room, "study") == ["study kiosk", "study second kiosk"]
    assert room.started == [] and sent(room, "poke") == []  # above the floor
    assert any(
        line.startswith("kiosk: the second kiosk — markup 55%") for line in room.echoed
    )


def test_after_a_logout_the_spell_is_up_and_the_kiosk_gone_so_another_is_grown():
    # 2026-10-16: a QUIT beside the kiosk, and "A jaggedly dendritic
    # crystalline kiosk shatters and evaporates into iridescent mist."; at
    # login the Spells window still said 61 roisaen and no kiosk was his.
    # The cast grew "a fibrous crystalline kiosk", the ledger intact, 0%.
    room = Room(
        after=["euhedral crystalline kiosk"],
        spells={kiosk.SPELL: 61},
        ledger=ours(reserve=97 * PLAT, pouch=5 * PLAT),
        grows="fibrous crystalline kiosk",
    )
    assert run(room) is None
    assert sent(room, "prepare") == ["prepare pria 30"]
    # The other's kiosk first, then the new one, listed first and named.
    assert sent(room, "study") == ["study kiosk", "study kiosk"]
    assert room.mine["markup"] == 55
    assert room.started == []  # 97 platinum kept on the tessera: no top-up


def test_a_gone_kiosk_is_not_grown_again_among_six_others():
    room = Room(
        after=[f"squat crystalline kiosk number {n}" for n in range(6)],
        spells={kiosk.SPELL: 61},
    )
    assert run(room) == "6 kiosks already stand here"
    assert sent(room, "prepare") == []


def test_the_other_kiosks_markups_are_read_and_said_but_ours_holds():
    rival = "iridescent crystal kiosk traced in softly lit starburst etchings"
    room = Room(before=[rival], mine=ours(), spells={kiosk.SPELL: 30})
    run(room)
    assert sent(room, "study") == ["study kiosk", "study second kiosk"]  # once each
    assert "kiosk: Sable's kiosk at 55%" in room.echoed
    assert room.mine["markup"] == 55  # markup= decides, not the rival's


def test_a_rival_read_lately_is_not_studied_again():
    rival = "iridescent crystal kiosk traced in softly lit starburst etchings"
    room = Room(after=[rival], mine=ours(), spells={kiosk.SPELL: 30})
    st = SimpleNamespace(target="kiosk", name=None, market={})
    room.list_room()
    script.market(room, st)
    script.market(room, st)
    assert sent(room, "study") == ["study second kiosk"]
    assert room.echoed == ["kiosk: Sable's kiosk at 55%"]


def test_a_markup_above_the_target_is_pushed_down():
    room = Room(mine=ours(markup=80), spells={kiosk.SPELL: 30})
    run(room, "markup=60")
    assert sent(room, "push") == ["push kiosk"] * 4
    assert room.mine["markup"] == 60


def test_a_kiosk_near_its_end_is_refreshed_and_keeps_its_markup():
    room = Room(mine=ours(), spells={kiosk.SPELL: 2})
    run(room)
    assert "prepare pria 30" in room.sent
    assert sent(room, "pull") == [] and sent(room, "push") == []


def test_a_kiosk_with_time_left_is_not_refreshed_and_the_wait_ends_at_its_recast():
    # A refresh sets the time to the new cast's: 8 left are thrown away.
    room = Room(mine=ours(), spells={kiosk.SPELL: 8})
    run(room)
    assert sent(room, "prepare") == []
    assert script.next_wait(room) == script.PASS_SECONDS  # 3 left at the next
    room.state.active_spells[kiosk.SPELL] = 5
    assert script.next_wait(room) == 3 * 60  # the next pass at 2 left


def test_stored_pouches_are_tapped_and_sold_with_finesse_cast_first():
    room = Room(mine=ours(pouch=51 * PLAT, bundle=5 * PLAT), spells={kiosk.SPELL: 30})
    run(room)
    order = [
        "discern Finesse",
        "prepare fin 80",  # DISCERN's estimate, strained and let go uncast
        "release",
        "prepare fin 78",
        "prepare fin 76",
        "prepare fin 74",
        "prepare fin 72",
        "tap kiosk",
        "stow my tessera",
        "ask appraiser to appraise my pouch",
        "sell my pouch",
        "stow my pouch",
    ]
    positions = [room.sent.index(command) for command in order]
    assert positions == sorted(positions)
    assert sent(room, "rub") == []  # dispensing pouches already
    assert "kiosk: sold the pouch for 72.3 plat" in room.echoed
    assert room.mine["bundle"] == 5 * PLAT  # under the tap: left on the tessera
    assert "stored 0 copper in pouches and 5 plat in bundles" in room.echoed[-2]
    assert sent(room, "cast") == ["cast"]  # no strained pattern was ever cast
    assert room.started == [("bank", [])]  # the pay banked, not carried
    assert casting.held_mana("Lanival", "Finesse") == 72


def test_finesse_starts_at_the_mana_it_last_took():
    first = Room(mine=ours(pouch=51 * PLAT), spells={kiosk.SPELL: 30})
    run(first)
    again = Room(mine=ours(pouch=51 * PLAT), spells={kiosk.SPELL: 30})
    run(again)
    assert sent(again, "discern") == []  # the day's answer, kept
    assert sent(again, "prepare")[0] == "prepare fin 72"


def test_a_lower_hold_steps_the_kept_mana_down_again():
    # Nerve damage or a thin room holds the caster under the kept figure.
    run(Room(mine=ours(pouch=51 * PLAT), spells={kiosk.SPELL: 30}))
    weaker = Room(mine=ours(pouch=51 * PLAT), spells={kiosk.SPELL: 30}, finesse_max=70)
    run(weaker)
    assert sent(weaker, "prepare") == ["prepare fin 72", "prepare fin 70"]
    assert casting.held_mana("Lanival", "Finesse") == 70


def test_a_refreshed_discern_keeps_the_held_mana_while_its_estimate_stands():
    casting._keep_discern("Lanival", "finesse", DISCERN_FINESSE, "finesse")
    casting._keep_held("Lanival", "Finesse", 72)
    casting._keep_discern("Lanival", "finesse", DISCERN_FINESSE, "finesse")
    assert casting.held_mana("Lanival", "Finesse") == 72
    grown = DISCERN_FINESSE.replace(
        "75 more, for a total of 80", "77 more, for a total of 82"
    )
    casting._keep_discern("Lanival", "finesse", grown, "finesse")
    assert casting.held_mana("Lanival", "Finesse") is None


def test_stored_bundles_are_rubbed_to_tapped_and_sold_at_the_tannery_rope_kept():
    room = Room(mine=ours(bundle=25 * PLAT), spells={kiosk.SPELL: 30, "Finesse": 20})
    run(room)
    assert sent(room, "prepare") == []  # Finesse up with time to spare
    assert sent(room, "rub") == ["rub kiosk"]
    assert room.sent.index("tap kiosk") < room.sent.index(
        "ask falken to appraise my bundle"
    )
    assert "sell my bundle" in room.sent
    assert "put my bundling rope in my sack" in room.sent
    assert room.state.room_uid == 1  # back at the kiosk


def test_a_mind_locked_trading_waits_with_the_value_on_the_tessera():
    room = Room(mine=ours(pouch=51 * PLAT), spells={kiosk.SPELL: 30}, trading=34)
    run(room)
    assert sent(room, "tap") == []


def test_six_kiosks_and_none_of_ours_stops_before_a_cast():
    room = Room(after=[f"squat crystalline kiosk number {n}" for n in range(6)])
    assert run(room) == "6 kiosks already stand here"
    assert sent(room, "prepare") == []
    assert not room.holds("tessera")  # put back


def test_no_tessera_no_cast():
    room = Room(tessera=False)
    assert run(room) == "no clear tessera on you — never a cast without it"
    assert sent(room, "prepare") == []


def test_no_bank_run_means_no_poke_so_the_purse_is_never_committed_whole():
    room = Room(mine=ours(reserve=0), spells={kiosk.SPELL: 30})
    room.can_bank = False
    run(room)
    assert sent(room, "poke") == []
    assert (
        "kiosk: the reserve was not topped up — no more top-ups this run" in room.echoed
    )


def test_the_tessera_reports_the_kiosk_from_any_room():
    reading = kiosk.read_report(REPORT)
    assert reading == {
        "room": "Grisgonda's, Appraisal Room",
        "markup": 60,
        "reserve": 229086,
        "pouch": 401589,
        "bundle": 265813,
    }
    assert kiosk.read_report(MISSING) is None


def test_status_reads_the_tessera_report_wherever_the_character_stands():
    room = Room(mine=ours(), spells={kiosk.SPELL: 30})
    room.state.room_uid = 2  # at the tannery, not the kiosk's room
    run(room, "status")
    assert room.sent == ["get my clear tessera", kiosk.REPORT, "stow my tessera"]
    assert room.echoed == [
        "kiosk: at [Grisgonda's, Appraisal Room] — markup 60%, reserve 22.9 plat, "
        "stored 40.2 plat in pouches and 26.6 plat in bundles, 30 roisaen left"
    ]


def test_options_are_platinum_and_the_markup_lands_on_a_step():
    options = script.parse_args(["markup=57", "reserve=200", "floor=80", "tap=10"])
    assert options == {
        "status": False,
        "markup": 55,
        "reserve": 200 * PLAT,
        "floor": 80 * PLAT,
        "tap": 10 * PLAT,
    }
