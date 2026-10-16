"""How ;skins sells — these tests are the manual. Walk to the nearest
tannery, take the worn bundle off, SELL it from the hand, keep the
rope, walk back. Wordings captured 2026-09-12 at Falken's Tannery."""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.engine.scripting import ScriptStopped

from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "skins_script", REPO / "scripts/skins.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

MAP = MapDB(
    [
        {"id": 100, "uid": [1], "title": ["[Town, Square]"], "wayto": {}},
        {
            "id": 8266,
            "uid": [9003],
            "title": ["[Falken's Tannery, Workshop]"],
            "tags": ["tannery", "crossing tannery"],
            "wayto": {},
        },
        {
            "id": 1200,
            "uid": [9004],
            "title": ["[Provincial Bank, Teller]"],
            "tags": ["bank"],
            "wayto": {},
        },
    ]
)
PROFILE = {"loot_container": "sack"}

# Captured 2026-09-12 on the first scripted sale: REMOVE's answer, and
# the tanner's for two pelts.
REMOVED = "You sling a lumpy bundle off from over your shoulder.\n"
SOLD = (
    "You ask the tanner Falken to buy a lumpy bundle.\n"
    "The tanner Falken ponders over the bundle for a while, then hands you 111 Kronars.\n"
    'Tanner Falken says, "And there\'s your rope back again."\n'
)
MISSING = "What were you referring to?\n"
# DEPOSIT ALL's answer, captured 2026-09-14 at the Provincial Bank.
DEPOSITED = (
    "The clerk slides a small metal box across the counter into which you drop "
    "all your Kronars.  She counts them carefully and records the deposit in "
    "her ledger.\n"
)


class Fake:
    """A handle whose answers come from a queue per command prefix."""

    def __init__(self, answers):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.sent = []
        self.echoed = []
        self.walks = []
        self.pending = []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(name="Lanival", room_uid=1)
        self.started = []  # (name, args) of the scripts this one ran
        self.can_start = True
        self.polls = 0  # is_running answers True this many times first

    # --- the handle's other-script API: ;skins bank runs ;bank ---
    def run(self, name, args=()):
        if not self.can_start:
            self.echoed.append(f"{name} is already running")
            return False
        self.started.append((name, list(args)))
        return True

    def is_running(self, name):
        self.polls -= 1
        return self.polls >= 0

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                text = queue.pop(0) if queue else ""
                self.pending = [line + "\n" for line in text.splitlines()]
                return
        if command.startswith("get my "):
            self.pending = [MISSING]  # nothing the test named

    def get(self, timeout=None, streams=("",)):
        if timeout == 0 or not self.pending:
            return None
        return self.pending.pop(0)

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def commands(fake):
    """The commands sent, minus the LOOK IN that names the loose skins
    (#401) — the bundle sale's own shape."""
    return [
        c
        for c in fake.sent
        if not c.startswith("look in my ")
        and not (c.startswith("get my ") and c.split()[2] in script.SKIN_NOUNS)
    ]


def walk(s, db, goals, describe="", avoid=()):
    s.walks.append(set(goals))
    s.state.room_uid = db.rooms[min(goals)]["uid"][0]
    return True


def test_sells_the_worn_bundle_keeps_the_rope_and_stays_at_the_tannery():
    # The start is usually the hunting ground: the first scripted run
    # walked back into the rats with the weapon stowed (2026-09-12).
    fake = Fake({"remove": [REMOVED], "sell": [SOLD]})
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == [{8266}]
    assert commands(fake) == [
        "remove my bundle",
        "sell my bundle",
        "put my bundling rope in my sack",
    ]
    assert "skins: sold the bundle for 111 Kronars" in fake.echoed


def test_a_bundle_already_in_hand_is_sold_without_a_remove():
    # 2026-09-14: a run stopped between REMOVE and SELL left the bundle
    # in the left hand, and the next run said "nothing to sell".
    fake = Fake({"sell": [SOLD]})
    fake.state.left_hand = {"noun": "bundle", "exist": "1", "name": "lumpy bundle"}
    fake.state.right_hand = {
        "noun": "handaxe",
        "exist": "2",
        "name": "oak-hafted handaxe",
    }
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert commands(fake) == ["sell my bundle", "put my bundling rope in my sack"]


def test_a_bundle_in_the_sack_is_fetched_when_none_is_worn():
    fake = Fake(
        {
            "remove": [MISSING],
            "get my bundle": ["You get a lumpy bundle from inside your canvas sack."],
            "sell": [SOLD],
        }
    )
    script.run(fake, ["back"], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == [{8266}, {100}]  # back: the walk home
    assert commands(fake)[:3] == [
        "remove my bundle",
        "get my bundle from my sack",
        "sell my bundle",
    ]


def test_a_stop_while_banking_stops_the_bank_it_started():
    # ;hunt stops its ;skins, and ;skins its ;bank (2026-09-28).
    fake = Fake({})
    fake.polls = 5
    killed = []
    fake.kill = killed.append

    def stopped(seconds):
        raise ScriptStopped()

    fake.sleep = stopped
    with pytest.raises(ScriptStopped):
        script.hand_to_bank(fake, [])
    assert killed == ["bank"]


def test_bank_runs_the_bank_script_and_waits_for_it():
    # The operator, 2026-09-20: "it should just do ;bank" — the banking
    # (the money-changer, DEPOSIT ALL, keep=N) lives in one script, and
    # ;skins carried a second copy of its last step. `back` walks home
    # once ;bank has ended; the teller is ;bank's to walk to.
    fake = Fake({"remove": [REMOVED], "sell": [SOLD]})
    fake.polls = 3
    script.run(fake, ["bank", "keep=500", "back"], MAP, walk_fn=walk, profile=PROFILE)
    assert commands(fake) == [
        "remove my bundle",
        "sell my bundle",
        "put my bundling rope in my sack",
    ]
    assert fake.started == [("bank", ["keep=500"])]
    assert fake.polls == -1  # waited until ;bank was no longer running
    assert fake.walks == [{8266}, {100}]
    assert "deposit all" not in fake.sent
    # Nothing sold still banks: a hunt's search coins are in the purse.
    fake = Fake({"remove": [MISSING], "get my bundle": [MISSING]})
    script.run(fake, ["bank"], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.started == [("bank", [])]
    # A ;bank already running is the operator's: said, left alone.
    fake = Fake({"remove": [REMOVED], "sell": [SOLD]})
    fake.can_start = False
    script.run(fake, ["bank"], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.started == []
    assert any("could not start ;bank" in text for text in fake.echoed)
    assert DEPOSITED  # the teller's line stays captured for ;bank's tests


def test_no_bundle_anywhere_stops_before_selling():
    fake = Fake({"remove": [MISSING], "get my bundle": [MISSING]})
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert "sell my bundle" not in fake.sent
    assert any("nothing to sell" in text for text in fake.echoed)


def test_the_other_not_found_wording_means_no_bundle_too():
    # The script's own check knew "What were you referring to?" alone and
    # would have SOLD on this answer; act.missing knows both (#407).
    could_not_find = "I could not find what you were referring to.\n"
    fake = Fake({"remove": [could_not_find], "get my bundle": [could_not_find]})
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert "sell my bundle" not in fake.sent
    assert any("nothing to sell" in text for text in fake.echoed)


def test_remove_what_means_no_bundle_worn_not_a_bundle_taken_off():
    # Captured 2026-10-03 (#450): with no bundle, REMOVE answered "Remove
    # what?", the script SOLD anyway and said "the tanner did not pay —
    # Sell what?" after every box farm with no kills.
    fake = Fake({"remove": ["Remove what?\n"], "get my bundle": [MISSING]})
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert "sell my bundle" not in fake.sent
    assert any("nothing to sell" in text for text in fake.echoed)


def test_a_tanner_who_does_not_pay_is_quoted_and_the_rope_left_alone():
    fake = Fake(
        {
            "remove": [REMOVED],
            "sell": ['The tanner Falken says, "I have no use for that."'],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert not any("rope" in command for command in fake.sent)
    assert any(
        "did not pay" in text and "no use for that" in text for text in fake.echoed
    )


def test_the_rope_is_put_away_by_its_whole_name_never_a_bare_rope():
    # The #399 class: a bare ROPE is the first rope of any kind, and a
    # looted lead rope sat beside the bundling rope that morning. The
    # hunt's ROPE names it whole, into the loot container or STOWed.
    fake = Fake({"remove": [REMOVED], "sell": [SOLD]})
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert "put my bundling rope in my sack" in fake.sent
    assert "put my rope in my sack" not in fake.sent
    fake = Fake({"remove": [REMOVED], "sell": [SOLD]})
    script.run(fake, [], MAP, walk_fn=walk, profile={"loot_container": ""})
    assert "stow my bundling rope" in fake.sent
    assert "stow my rope" not in fake.sent


LOOKED = (
    "In the canvas sack you see a round cambrinth flake, a badger pelt, a "
    "curved claw, a badger pelt, some bundling rope and a cotton rag.\n"
)


def test_the_look_in_answer_names_the_nouns_present():
    assert script.listed_nouns(LOOKED) == [
        "flake",
        "pelt",
        "claw",
        "pelt",
        "rope",
        "rag",
    ]
    assert script.listed_nouns("There is nothing in there.\n") == []
    assert script.listed_nouns("What were you referring to?\n") is None


def test_loose_skins_in_the_sack_are_named_and_left_there():
    # #401 (the operator, 2026-10-01): only a bundle is sold. A loose skin
    # is kept on purpose or says a hunt could not bundle it — the 22
    # loose pelts #399 left were sold unseen that morning.
    fake = Fake(
        {
            "remove": [REMOVED],
            "sell my bundle": [SOLD],
            "look in my sack": [LOOKED],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert "sell my bundle" in fake.sent
    assert not any(c.startswith(("sell my pelt", "sell my claw")) for c in fake.sent)
    assert not any(c.startswith(("get my pelt", "get my claw")) for c in fake.sent)
    assert (
        "skins: 2 pelt(s), 1 claw(s) loose in the sack — left there; "
        "only a bundle is sold"
    ) in fake.echoed
    assert fake.sent.count("look in my sack") == 1


def test_a_skin_left_in_hand_is_named_not_sold():
    # #262 left a pelt in the hand when no container had room.
    fake = Fake(
        {
            "remove": [MISSING],
            "get my bundle": [MISSING],
            "look in my sack": ["In the canvas sack you see a cotton rag.\n"],
        }
    )
    fake.state.left_hand = {"noun": "pelt", "exist": "3", "name": "badger pelt"}
    fake.state.right_hand = None
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert "sell my pelt" not in fake.sent
    assert "skins: a pelt in hand — left there; only a bundle is sold" in fake.echoed


def test_no_loose_skins_says_nothing_about_them():
    fake = Fake(
        {
            "remove": [REMOVED],
            "sell my bundle": [SOLD],
            "look in my sack": ["In the canvas sack you see some bundling rope.\n"],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert not any("only a bundle is sold" in t for t in fake.echoed)


def test_no_tannery_on_the_map_says_so():
    fake = Fake({})
    script.run(
        fake,
        [],
        MapDB([{"id": 1, "uid": [1], "title": ["[A]"], "wayto": {}}]),
        walk_fn=walk,
        profile=PROFILE,
    )
    assert commands(fake) == []
    assert any("no room tagged 'tannery'" in text for text in fake.echoed)


# --- the bundle and the rope by their ids (#456) ---

GEAR = [
    {"exist": "300", "name": "a woven straw tote", "noun": "tote", "worn": True},
    {
        "exist": "301",
        "name": "some bundling rope",
        "noun": "rope",
        "worn": False,
        "container_exist": "300",
    },
    {"exist": "302", "name": "a lumpy bundle", "noun": "bundle", "worn": True},
    {
        "exist": "303",
        "name": "a lumpy bundle",
        "noun": "bundle",
        "worn": False,
        "container_exist": "300",
    },
]


def test_the_worn_bundle_is_removed_by_its_id_and_a_stale_id_falls_back(monkeypatch):
    from client.game import items

    monkeypatch.setattr(items, "_STALE", set())
    sent = []
    answers = {"remove #302": "Remove what?", "remove my bundle": "Remove what?"}

    def ask(s, command):
        sent.append(command)
        return answers.get(command, "You get a lumpy bundle from inside your tote.")

    monkeypatch.setattr(script, "ask", ask)
    s = SimpleNamespace(
        state=SimpleNamespace(possessions=GEAR, left_hand=None, right_hand=None)
    )
    assert script.take_bundle(s, "tote")
    # The worn one sold since login: forgotten, the noun, then the carried one.
    assert sent == ["remove #302", "remove my bundle", "get #303"]
    sent.clear()
    answers["remove my bundle"] = "You remove a lumpy bundle."
    script.take_bundle(s, "tote")
    assert sent == ["remove my bundle"]  # #302 is not tried again


# --- a Trader's kiosk in the tanner's room (#567) ---

# The Crossing's tannery as the logs list it, 2026-10.
TANNERY = (
    "You also see a stellate crystalline kiosk, a luminescent Iridius crystal "
    "plinth protected by a faceted glass-like dragon, a sturdy door, the "
    "tanner Falken, a stuffed vulture and a stuffed stag's head."
)
# ASK FALKEN TO APPRAISE MY BUNDLE, captured 2026-09-12 (the SELL paid 111).
APPRAISED = (
    "You ask the tanner Falken to appraise a lumpy bundle.\n"
    "The tanner Falken looks the lumpy bundle over carefully, then whispers, "
    '"I can give 111 Kronars for it."\n'
)
# Not captured yet: TIE's answer and the kiosk's quote are assumptions; the
# sale line is the room's third-person one (2026-10-03) told to "you".
TIED = "You tie off your lumpy bundle.\n"
KIOSK_SOLD = (
    "A stellate crystalline kiosk ripples like water, and the surface spirals "
    "open, revealing an empty interior chamber.  You place your bundle in the "
    "crystalline kiosk, which chimes and closes seamlessly.  After a brief "
    "moment, the kiosk pulses with soft light and a tidy pile of coins rises "
    "from its surface, which you quickly pocket.\n"
)


def quoted(amount):
    return f"The kiosk offers you {amount} for your bundle.\n"


class KioskFake(Fake):
    """The bundle in hand in the tannery; a kiosk's sale line takes it."""

    def __init__(self, answers, room=TANNERY):
        super().__init__(answers)
        self.state.room_objs = room
        self.state.left_hand = {"noun": "bundle", "exist": "1", "name": "lumpy bundle"}
        self.state.right_hand = None

    def put(self, command):
        super().put(command)
        if any("quickly pocket" in line for line in self.pending):
            self.state.left_hand = None


def test_every_kiosk_and_plinth_in_the_listing_is_a_give_target():
    assert script.kiosks(TANNERY) == ["kiosk", "plinth"]
    two = "You also see a lamellar crystalline kiosk, a stellate crystalline kiosk."
    assert script.kiosks(two) == ["kiosk", "second kiosk"]
    assert script.kiosks("You also see a sturdy door, the tanner Falken.") == []


def test_an_amount_reads_as_copper_kronars():
    assert script.kronars("I can give 111 Kronars for it") == 111
    assert script.kronars("1 gold, 5 silver and 1 bronze Kronars, value 9 gold") == 1510
    assert script.kronars("100 Lirums") == 125  # money.KRONAR_RATES
    assert script.kronars("The kiosk only buys tied bundles.") is None


def test_a_kiosk_quoting_above_the_tanner_buys_the_tied_bundle():
    fake = KioskFake(
        {
            "ask falken to appraise": [APPRAISED],
            "tie": [TIED],
            "give my bundle to kiosk": [quoted("1 silver Kronars")],
            "give my bundle to plinth": [
                quoted("1 silver and 3 bronze Kronars"),
                KIOSK_SOLD,
            ],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert commands(fake) == [
        "ask falken to appraise my bundle",
        "tie my bundle",
        "give my bundle to kiosk",
        "give my bundle to plinth",
        "give my bundle to plinth",  # the same GIVE again: the sale
        "ask falken for rope",  # the kiosk kept the rope; the tanner's is free
        "put my bundling rope in my sack",
    ]
    assert (
        "skins: sold the bundle to the plinth for 1.3 silver Kronars"
        " — the tanner offered 1.11 silver Kronars"
    ) in fake.echoed


def test_the_tanner_buys_when_no_kiosk_beats_his_quote():
    fake = KioskFake(
        {
            "ask falken to appraise": [APPRAISED],
            "tie": [TIED],
            "give my bundle to kiosk": [quoted("1 silver Kronars")],
            "give my bundle to plinth": [quoted("111 Kronars")],  # level is no gain
            "sell": [SOLD],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.sent.count("give my bundle to kiosk") == 1
    assert fake.sent.count("give my bundle to plinth") == 1
    assert "sell my bundle" in fake.sent
    assert "ask falken for rope" not in fake.sent  # the tanner hands it back
    assert (
        "skins: no kiosk beats the tanner's 1.11 silver Kronars — selling to the tanner"
    ) in fake.echoed
    assert "skins: sold the bundle for 111 Kronars" in fake.echoed


def test_a_stale_quote_is_quoted_again_then_sold():
    # The plinth's quote came after the kiosk's: the kiosk's 10 seconds
    # may be gone, so its GIVE quotes again and the next one sells.
    fake = KioskFake(
        {
            "ask falken to appraise": [APPRAISED],
            "give my bundle to kiosk": [quoted("2 silver Kronars")] * 2 + [KIOSK_SOLD],
            "give my bundle to plinth": [quoted("1 silver Kronars")],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.sent.count("give my bundle to kiosk") == 3
    assert "sell my bundle" not in fake.sent
    assert any("sold the bundle to the kiosk for 2 silver" in t for t in fake.echoed)


def test_a_quote_again_below_the_tanner_goes_to_the_tanner():
    # A kiosk short of funds since its first quote (part-pay wordings
    # not captured yet): the lower quote loses to the tanner.
    fake = KioskFake(
        {
            "ask falken to appraise": [APPRAISED],
            "give my bundle to kiosk": [
                quoted("2 silver Kronars"),
                quoted("50 Kronars"),
            ],
            "sell": [SOLD],
        },
        room="You also see a stellate crystalline kiosk, the tanner Falken.",
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.sent.count("give my bundle to kiosk") == 2
    assert "sell my bundle" in fake.sent
    assert any("the kiosk did not buy" in t for t in fake.echoed)


def test_an_unread_kiosk_answer_is_reported_and_the_tanner_buys():
    fake = KioskFake(
        {
            "ask falken to appraise": [APPRAISED],
            "give my bundle to kiosk": ["The kiosk only buys tied bundles.\n"],
            "give my bundle to plinth": ["The plinth is out of funds.\n"],
            "sell": [SOLD],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert "sell my bundle" in fake.sent
    assert any(
        "unrecognized kiosk quote answer" in t and "please report it" in t
        for t in fake.echoed
    )


def test_no_tanner_quote_sells_to_the_tanner_without_asking_a_kiosk():
    # A tanner the listing does not name, or one who quotes nothing.
    fake = KioskFake(
        {"sell": [SOLD]}, room="You also see a stellate crystalline kiosk."
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert not any(c.startswith(("give", "tie", "ask")) for c in fake.sent)
    assert "sell my bundle" in fake.sent
    assert any("no tanner's quote" in t for t in fake.echoed)
