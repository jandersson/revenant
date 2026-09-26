"""How ;boxes trains — these tests are the manual. It takes each box out
of the loot container, identifies and disarms the trap, identifies and
picks the lock, opens the box, takes the loot and disposes of the
empty box; a box past the reading is put back, a sprung trap that
hurts ends the run, a typed return ends it after the box in hand
(#293)."""

import importlib.util
import pathlib
from types import SimpleNamespace

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "boxes_script", REPO / "scripts/boxes.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

# The wordings are pick.lic's and the wiki's until captured (2026-09-23).
SACK = (
    "In the canvas sack you see a dented iron box, some bundling rope "
    "and a mildewy deobar crate.\n"
)
SIMPLE_TRAP = "The dented iron box will be a simple matter for you to disarm.\n"
DISARMED = (
    "You carefully bend the head of the needle so that it can no longer spring.\n"
)
NO_TRAP = "Looking closely you see a bent needle sticks harmlessly out of the lock.\n"
JUNK_LOCK = (
    "The lock is a trivially constructed piece of junk barely worth your time.\n"
)
UNLOCKED = "With a click you remove your lockpick and open and remove the lock.\n"
OPENED = "In the iron box you see some coins and a ruby.\n"
COINS = "You pick up 12 copper Kronars.\n"
GOT = "You get a ruby from inside your iron box.\n"
LONGSHOT = "Disarming the mildewy deobar crate would be a longshot.\n"
ACID = "A stream of corrosive acid sprays out from the lock and burns your hand!\n"

PROFILE = {
    "loot_container": "sack",
    "gem_pouch": "pouch",
    "lockpick": "lockpick",
    "lockpick_ring": "",
    "health_floor": 60,
    "wound_floor": "off",
}


class Fake:
    """A handle answering from a table keyed by command prefix; the
    Locksmithing mindstate advances one step per DISARM or PICK."""

    def __init__(self, answers, mindstates=(1,), stop_after=None, health=100):
        self.answers = answers
        self.mindstates = list(mindstates)
        self.stop_after = stop_after
        self.worked = 0
        self.sent, self.echoed = [], []
        self.dead = False
        self.args = []
        self.status = SimpleNamespace(health=health, stunned=False)
        self.state = SimpleNamespace(
            name="Lanival",
            experience={
                "Locksmithing": {
                    "rank": 1,
                    "percent": 0,
                    "mindstate": self.mindstates.pop(0),
                }
            },
            hostiles={},
            injuries={},
            room_objs="You also see a bucket.",
            left_hand=None,
            right_hand=None,
        )

    def ask(self, s, command, *_):
        self.sent.append(command)
        for prefix, answer in self.answers:
            if command.startswith(prefix):
                if callable(answer):
                    answer = answer(command)
                if prefix.startswith(("disarm", "pick")) and "identify" not in command:
                    self.worked += 1
                    if self.mindstates:
                        self.state.experience["Locksmithing"]["mindstate"] = (
                            self.mindstates.pop(0)
                        )
                return answer
        return ""

    def put(self, command):
        self.sent.append(command)

    def get(self, timeout=None, streams=("",)):
        return None

    def command(self, timeout=None):
        if self.stop_after is not None and self.worked >= self.stop_after:
            self.stop_after = None
            return "return"
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def one_easy_box():
    """A table: one box in the sack, a simple trap, a junk lock, coins
    and a ruby inside; the crate reads as a longshot."""
    return [
        ("look in my sack", SACK),
        (
            "get box from my sack",
            "You get a dented iron box from inside your canvas sack.\n",
        ),
        ("get my lockpick", "You get a lockpick from inside your backpack.\n"),
        (
            "disarm my box identify",
            lambda c: SIMPLE_TRAP if _DISARMS["count"] < 1 else NO_TRAP,
        ),
        ("disarm my box", disarmed),
        ("pick my box identify", JUNK_LOCK),
        ("pick my box", UNLOCKED),
        ("open my box", OPENED),
        ("get coins from my box", COINS),
        ("get ruby from my box", GOT),
        ("put my ruby in my pouch", "You put your ruby in your gem pouch.\n"),
        ("put my box in bucket", "You drop a dented iron box in a bucket.\n"),
        (
            "get crate from my sack",
            "You get a mildewy deobar crate from inside your canvas sack.\n",
        ),
        ("disarm my crate identify", LONGSHOT),
        ("put my crate in my sack", "You put your crate in your canvas sack.\n"),
    ]


_DISARMS = {"count": 0}


def disarmed(command):
    """The DISARM success, counted: IDENTIFY reads no trap after it."""
    _DISARMS["count"] += 1
    return DISARMED


def run(fake, args=(), profile=None, droppable=("box",)):
    _DISARMS["count"] = 0
    script.probe = SimpleNamespace(ask=fake.ask)
    # The script's own view of discard.py, never the shared module: a
    # patch on it leaked into test_discard and test_mechlore once.
    script.discard = SimpleNamespace(
        droppable=lambda item: item in droppable,
        drop=lambda s, item, ask: ask(s, f"put my {item} in bucket"),
    )
    script.run_loop(
        fake, dict(PROFILE, **(profile or {})), script.parse_args(list(args))
    )
    return "\n".join(fake.echoed)


def test_a_box_is_taken_disarmed_picked_opened_emptied_and_binned():
    fake = Fake(one_easy_box(), mindstates=[1, 3, 5, 7])
    out = run(fake)
    assert fake.sent[:3] == ["look in my sack", "sit", "get box from my sack"]
    assert "disarm my box identify" in fake.sent
    assert "disarm my box" in fake.sent  # a simple trap: plain caution (4/17)
    assert "get my lockpick" in fake.sent
    assert "pick my box identify" in fake.sent
    assert "pick my box quick" in fake.sent  # a junk lock: quick (3/17)
    assert "stow my lockpick" in fake.sent  # before the loot comes out
    assert fake.sent.index("open my box") > fake.sent.index("stow my lockpick")
    assert "get coins from my box" in fake.sent
    assert "get ruby from my box" in fake.sent
    assert "put my ruby in my pouch" in fake.sent
    assert "put my box in bucket" in fake.sent
    assert "drop my box" not in fake.sent
    assert "the box's trap is down (plain, read 4/17)" in out
    assert "the box is unlocked (quick, read 3/17)" in out
    assert "the box opened — 2 item(s) out (1 box(es) so far)" in out
    assert fake.sent[-1] == "stand"


def test_a_longshot_reading_puts_the_box_back_for_a_better_locksmith():
    fake = Fake(one_easy_box(), mindstates=[1, 3, 5, 7])
    out = run(fake)
    assert "get crate from my sack" in fake.sent
    assert "disarm my crate identify" in fake.sent
    assert "disarm my crate careful" not in fake.sent
    assert "put my crate in my sack" in fake.sent
    assert "the crate's trap reads 11/17 — 11 or harder, too hard" in out
    assert "the crate goes back into the sack — for a better locksmith" in out
    assert "every box tried — 1 opened, 1 kept" in out


def test_a_second_box_of_a_kept_noun_is_taken_by_ordinal():
    answers = one_easy_box()
    answers[0] = (
        "look in my sack",
        "In the canvas sack you see a mildewy deobar crate and a mildewy deobar crate.\n",
    )
    answers.append(
        (
            "get second crate from my sack",
            "You get a mildewy deobar crate from inside your canvas sack.\n",
        )
    )
    fake = Fake(answers, mindstates=[1])
    run(fake)  # the ordinal is the point
    gets = [c for c in fake.sent if c.startswith("get") and "crate" in c]
    assert gets == ["get crate from my sack", "get second crate from my sack"]


def test_a_box_not_on_the_droppable_list_goes_back_into_the_container():
    fake = Fake(one_easy_box(), mindstates=[1, 3, 5, 7])
    out = run(fake, droppable=())
    assert "put my box in bucket" not in fake.sent
    assert "drop my box" not in fake.sent
    assert "put my box in my sack" in fake.sent
    assert "not on settings.json's droppable list" in out


def test_a_worn_ring_means_no_lockpick_is_fetched():
    fake = Fake(one_easy_box(), mindstates=[1, 3, 5, 7])
    run(fake, profile={"lockpick_ring": "ring"})
    assert "get my lockpick" not in fake.sent
    assert "stow my lockpick" not in fake.sent
    assert "pick my box quick" in fake.sent


def test_an_empty_ring_falls_back_to_the_loose_lockpick():
    # 2026-09-26: the ring's last pick broke on a crate; the next run's
    # PICK answered "Find a more appropriate tool and try again!", was
    # read as a lock wanting another kind of pick, and the crate went back
    # with a loose lockpick sitting in the pack.
    answers = one_easy_box()
    picks = {"n": 0}

    def identify(command):
        picks["n"] += 1
        return (
            "Find a more appropriate tool and try again!\n"
            if picks["n"] == 1
            else JUNK_LOCK
        )

    answers[5] = ("pick my box identify", identify)
    fake = Fake(answers, mindstates=[1, 3, 5, 7])
    out = run(fake, profile={"lockpick_ring": "ring"})
    assert "the lockpick ring is empty — the loose lockpick from here" in out
    assert "wants another kind of lockpick" not in out
    assert "get my lockpick" in fake.sent
    assert fake.sent.count("pick my box identify") == 2
    assert "the box opened" in out


def test_the_rings_last_pick_breaking_switches_to_the_loose_one():
    answers = one_easy_box()
    last = (
        "You quickly notice the lockpick is bent beyond practical use.  With a "
        "grimace, you discard the now useless lockpick.\n"
        "You look down at your lockpick ring and realize that was the last one!\n"
    )
    tries = {"n": 0}

    def pick(command):
        tries["n"] += 1
        return last if tries["n"] == 1 else UNLOCKED

    answers[6] = ("pick my box", pick)
    fake = Fake(answers, mindstates=[1, 3, 5, 7])
    out = run(fake, profile={"lockpick_ring": "ring"})
    assert "the lockpick broke" in out
    assert "the lockpick ring is empty" in out
    assert "get my lockpick" in fake.sent
    assert "the box opened" in out


def test_the_careful_word_and_stand_override_the_reading_and_the_sit():
    fake = Fake(one_easy_box(), mindstates=[1, 3, 5, 7])
    run(fake, ["careful", "stand"])
    assert "disarm my box careful" in fake.sent
    assert "pick my box careful" in fake.sent
    assert "sit" not in fake.sent


def test_a_sprung_trap_that_drops_the_health_below_the_floor_ends_the_run():
    answers = one_easy_box()
    answers[3] = ("disarm my box identify", SIMPLE_TRAP)
    answers[4] = ("disarm my box", ACID)
    fake = Fake(answers, mindstates=[1, 3], health=40)
    out = run(fake)
    assert "a trap sprung — 'A stream of corrosive acid sprays out" in out
    assert "health 40% below the floor of 60% — stopping" in out
    assert "put my box in my sack" in fake.sent  # the box back, the run ends
    assert "pick my box identify" not in fake.sent
    assert fake.sent[-1] == "stand"


def test_a_sprung_trap_that_did_not_hurt_is_tried_again():
    answers = one_easy_box()
    tries = {"n": 0}

    def disarm(command):
        tries["n"] += 1
        return ACID if tries["n"] == 1 else disarmed(command)

    answers[4] = ("disarm my box", disarm)
    fake = Fake(answers, mindstates=[1, 3, 5, 7, 9])
    out = run(fake)
    assert "a trap sprung" in out
    assert fake.sent.count("disarm my box") == 2
    assert "the box opened" in out


def test_no_lockpick_and_no_ring_ends_the_run_with_the_shop_named():
    answers = one_easy_box()
    answers[2] = ("get my lockpick", "What were you referring to?\n")
    fake = Fake(answers, mindstates=[1, 3])
    out = run(fake)
    assert "no lockpick to pick with — Ragge's Locksmithing" in out
    assert "no lockpick — stopping" in out
    assert "pick my box identify" not in fake.sent


def test_an_empty_container_and_an_unreadable_one_are_said():
    fake = Fake([("look in my sack", "In the canvas sack you see a cotton rag.\n")])
    assert "no boxes in the sack — nothing to pick" in run(fake)
    fake = Fake([("look in my sack", "What were you referring to?\n")])
    assert "cannot read the sack" in run(fake)
    fake = Fake([])
    assert "no container — source=" in run(fake, profile={"loot_container": ""})


def test_the_source_word_names_another_container():
    answers = [(p.replace("my sack", "my backpack"), a) for p, a in one_easy_box()]
    fake = Fake(answers, mindstates=[1, 3, 5, 7])
    run(fake, ["source=backpack"])
    assert fake.sent[0] == "look in my backpack"
    assert "get box from my backpack" in fake.sent


def test_a_typed_return_ends_after_the_box_in_hand():
    fake = Fake(one_easy_box(), mindstates=[1, 3, 5, 7], stop_after=1)
    out = run(fake)
    assert "the box opened" in out
    assert "get crate from my sack" not in fake.sent
    assert "stopping as asked" in out


def test_mind_lock_holds_and_once_exits(monkeypatch):
    fake = Fake(one_easy_box(), mindstates=[34])
    out = run(fake, ["once"])
    assert "Locksmithing at 34/34 — done" in out
    assert "get box from my sack" not in fake.sent

    monkeypatch.setattr(script, "LOCK_POLL", 1)
    fake = Fake(one_easy_box(), mindstates=[34, 27, 5, 7, 9])
    fake.sleep = lambda seconds: (
        fake.state.experience["Locksmithing"].__setitem__(
            "mindstate", fake.mindstates.pop(0)
        )
        if fake.mindstates
        else None
    )
    out = run(fake)
    assert "mind-locked (34/34) — holding until it drains" in out
    assert "drained to 27/34 — picking again" in out
    assert "the box opened" in out


def test_danger_ends_the_run_and_the_exp_window_without_the_skill_is_asked():
    fake = Fake(one_easy_box())
    fake.state.hostiles = {"1": True}
    fake.state.room_objs = ""
    out = run(fake)
    assert "hostiles in the room — stopping" in out

    fake = Fake([("exp locksmithing", "Locksmithing:   1 11% dabbling  (2/34)\n")])
    fake.state.experience = {}
    run(fake)
    assert fake.sent[0] == "exp locksmithing"
    assert fake.state.experience["Locksmithing"]["mindstate"] == 2


def test_hindering_gear_is_said_once_a_run():
    # Captured 2026-09-23: plate and brass knuckles hinder every attempt.
    answers = one_easy_box()
    hindered = (
        "Your armor hinders your attempt.\nYour brass knuckles hinders your attempt.\n"
        + SIMPLE_TRAP
    )
    answers[3] = (
        "disarm my box identify",
        lambda c: hindered if _DISARMS["count"] < 1 else NO_TRAP,
    )
    fake = Fake(answers, mindstates=[1, 3, 5, 7])
    out = run(fake)
    line = (
        "boxes: Your armor hinders your attempt. Your brass knuckles hinders your "
        "attempt. — remove it for better odds"
    )
    assert out.count(line) == 1
    assert "the box opened" in out


def test_a_box_past_the_reading_gets_one_identify_and_goes_straight_back():
    # The practice mode (DISARM IDENTIFY over and over on a too-hard
    # box) is gone: on 2026-09-23 it sent eighty identifies in forty
    # seconds — the game answers an identify of a trap already read at
    # once, with no roundtime — and Locksmithing stayed at 0/34. One
    # identify reads the box, and it goes back; the run ends when every
    # box has been tried, and `nopractice` is no longer a word.
    answers = [
        ("look in my sack", "In the canvas sack you see a mildewy deobar crate.\n"),
        (
            "get crate from my sack",
            "You get a mildewy deobar crate from inside your canvas sack.\n",
        ),
        ("disarm my crate identify", LONGSHOT),
        ("put my crate in my sack", "You put your crate in your canvas sack.\n"),
    ]
    fake = Fake(answers, mindstates=[1, 1, 1])
    out = run(fake, ["nopractice"])
    assert fake.sent.count("disarm my crate identify") == 1
    assert "disarm my crate careful" not in fake.sent
    assert "practising" not in out
    assert "the crate goes back into the sack — for a better locksmith" in out
    assert "every box tried — 0 opened, 1 kept for a better locksmith" in out


FROG_PRAYER = (
    "While checking the crate with a careful eye, you notice a lumpy green rune "
    "hidden inside the box near the lock.\nPrayer would be a good start for any "
    "attempt of yours at disarming the mildewy deobar crate.\n"
)
LAUGHING_LONGSHOT = (
    "Examining the box for traps reveals a tiny glass tube filled with a black "
    "gaseous substance of some sort and a tiny hammer at the ready to do what it "
    "was designed for.\n" + LONGSHOT
)
FLEA_LONGSHOT = (
    "Imbedded in the front of the iron crate is a small glass tube of milky-white "
    "opacity.\n" + LONGSHOT
)
# Captured 2026-09-23: a careful disarm that got nowhere.
NO_PROGRESS = (
    "You work with the trap for a while but are unable to make any progress.\n"
)


def crate_reading(identify):
    """The easy-box table with the crate's identify answering `identify`
    and every careful disarm of it getting nowhere."""
    answers = [
        (prefix, identify if prefix == "disarm my crate identify" else answer)
        for prefix, answer in one_easy_box()
    ]
    answers.append(("disarm my crate", NO_PROGRESS))
    return answers


def test_a_nuisance_trap_past_the_threshold_gets_a_careful_try():
    # 2026-09-25: at Locksmithing 3 both grendel boxes read 11-12, and
    # both traps were a toad and a joke — the operator: accept the risk.
    fake = Fake(crate_reading(FROG_PRAYER), mindstates=[1, 3, 5, 7])
    out = run(fake)
    assert "disarm my crate careful" in fake.sent
    assert (
        "the crate's trap reads 12/17 — a frog trap, a nuisance at worst: trying careful"
        in out
    )
    assert "put my crate in my sack" in fake.sent  # no progress: kept


def test_a_deadly_trap_past_the_threshold_still_goes_back():
    fake = Fake(crate_reading(FLEA_LONGSHOT), mindstates=[1, 3, 5, 7])
    out = run(fake)
    assert "disarm my crate careful" not in fake.sent
    assert "the crate's trap reads 11/17 — 11 or harder, too hard" in out


def test_a_trap_that_hits_the_room_waits_for_an_empty_room():
    fake = Fake(crate_reading(LAUGHING_LONGSHOT), mindstates=[1, 3, 5, 7])
    fake.state.room_players = ["Uthmor"]
    out = run(fake)
    assert "disarm my crate careful" not in fake.sent
    assert "laughing gas trap would catch Uthmor too — left for an empty room" in out


def test_safe_puts_back_even_a_nuisance_trap():
    fake = Fake(crate_reading(FROG_PRAYER), mindstates=[1, 3, 5, 7])
    out = run(fake, args=["safe"])
    assert "disarm my crate careful" not in fake.sent
    assert "the crate's trap reads 12/17 — 11 or harder, too hard" in out


def test_a_lock_past_the_threshold_is_picked_careful_anyway():
    answers = [
        (prefix, LONGSHOT_LOCK if prefix == "pick my box identify" else answer)
        for prefix, answer in one_easy_box()
    ]
    fake = Fake(answers, mindstates=[1, 3, 5, 7])
    out = run(fake)
    assert "pick my box careful" in fake.sent
    assert "trying careful anyway (a lock only risks the pick)" in out


LONGSHOT_LOCK = "Opening the dented iron box would be a longshot.\n"


def test_a_sprung_trap_that_floors_the_box_picks_it_up_and_the_stun_is_waited(
    monkeypatch,
):
    # 2026-09-25: the laughing gas left the skippet on the floor and the
    # character prone; "You are still stunned." answered every DISARM
    # after, and the run skipped every box and left the skippet there.
    from test_boxes import CAPTURED_LAUGHING_SPRUNG

    fake = None
    answers_seen = {"disarm": 0}

    def disarm(command):
        answers_seen["disarm"] += 1
        if answers_seen["disarm"] == 1:
            fake.state.room_objs = "You also see a mildewy deobar crate and a bucket."
            fake.status.stunned = True
            fake.status.posture = "prone"
            return CAPTURED_LAUGHING_SPRUNG
        if answers_seen["disarm"] == 2:
            return "You are still stunned.\n"
        return NO_PROGRESS

    answers = crate_reading(FROG_PRAYER)
    answers = [(p, disarm if p == "disarm my crate" else a) for p, a in answers]
    fake = Fake(answers, mindstates=[1, 3, 5, 7])
    fake.status.posture = "sitting"

    def sleep(seconds):
        fake.status.stunned = False  # the stun wears off while waited

    fake.sleep = sleep
    out = run(fake)
    assert "get crate" in fake.sent  # off the floor, no "my"
    assert "the crate was knocked to the floor — picked back up" in out
    assert "sit" in fake.sent[fake.sent.index("get crate") :]
    assert not any("would not identify" in line for line in out.splitlines())


def test_tries_sets_how_many_attempts_a_lock_gets_before_the_box_goes_back():
    answers = [
        (prefix, LONGSHOT_LOCK if prefix == "pick my box identify" else answer)
        for prefix, answer in one_easy_box()
    ]
    answers = [
        (p, "You are unable to make any progress towards opening the lock.\n")
        if p == "pick my box"
        else (p, a)
        for p, a in answers
    ]
    fake = Fake(answers, mindstates=[1] * 40)
    run(fake, args=["tries=12"])
    assert fake.sent.count("pick my box careful") == 12


# #323: a coffer in the backpack, the loot container (the sack) without
# boxes — every run said "no boxes in the sack" and the coffer sat.
POSSESSIONS_WITH_A_COFFER = [
    {"exist": "1", "name": "a large canvas sack", "noun": "sack", "depth": 0},
    {
        "exist": "2",
        "name": "a cotton rag",
        "noun": "rag",
        "container_exist": "1",
        "depth": 1,
    },
    {"exist": "3", "name": "a rugged backpack", "noun": "backpack", "depth": 0},
    {
        "exist": "4",
        "name": "a plain steel coffer",
        "noun": "coffer",
        "container_exist": "3",
        "depth": 1,
    },
    {
        "exist": "5",
        "name": "an iron mortar",
        "noun": "mortar",
        "container_exist": "3",
        "depth": 1,
    },
]
BACKPACK = "In the rugged backpack you see an iron mortar and a plain steel coffer.\n"
COFFER_LONGSHOT = "Disarming the plain steel coffer would be a longshot.\n"


def test_a_box_in_another_container_is_worked_and_put_back_there():
    fake = Fake(
        [
            ("look in my sack", "In the canvas sack you see a cotton rag.\n"),
            ("look in my backpack", BACKPACK),
            (
                "get coffer from my backpack",
                "You get a plain steel coffer from inside your rugged backpack.\n",
            ),
            ("disarm my coffer identify", COFFER_LONGSHOT),
            ("put my coffer in my backpack", "You put your coffer in your backpack.\n"),
        ],
        mindstates=[1, 3],
    )
    fake.state.possessions = POSSESSIONS_WITH_A_COFFER
    out = run(fake)
    assert "1 box(es) in the backpack" in out
    assert "get coffer from my backpack" in fake.sent
    assert "put my coffer in my backpack" in fake.sent
    assert "1 kept for a better locksmith" in out


def test_a_named_source_works_that_container_alone():
    fake = Fake(
        [("look in my sack", "In the canvas sack you see a cotton rag.\n")],
        mindstates=[1],
    )
    fake.state.possessions = POSSESSIONS_WITH_A_COFFER
    out = run(fake, ["source=sack"])
    assert "look in my backpack" not in fake.sent
    assert "no boxes in the sack — nothing to pick" in out


# --- the empty ring refilled at Ragge's (the operator, 2026-09-26) ---

# Ragge's haggle, captured 2026-09-26: ORDER by name, OFFER the price.
RAGGE_QUOTE = (
    "Ragge sighs.  \"Despite the rarity of this lockpick, I'm prepared to offer "
    'it to you for 125 kronars."\n'
)
RAGGE_BOUGHT = "Ragge hands over your lockpick.\n"
ON_RING = "You put your lockpick on your lockpick ring.\n"


def _refill_world(monkeypatch, carried=2000):
    import client.game.bank as bank
    import client.game.mapdb as mapdb
    import client.game.walker as walker

    walked, withdrawn = [], []
    db = SimpleNamespace(rooms_tagged=lambda tag: [19125] if tag == "locksmith" else [])
    monkeypatch.setattr(mapdb.MapDB, "load", classmethod(lambda cls, path=None: db))
    monkeypatch.setattr(
        walker,
        "walk",
        lambda s, db, goals, describe="", avoid=(): walked.append(set(goals)) or True,
    )

    def withdraw(s, db, walk, ask, prefix, copper, currency, retry=""):
        withdrawn.append(copper)
        return True

    monkeypatch.setattr(bank, "withdraw", withdraw)
    wealth = f"Wealth:\n  {carried} copper Kronars ({carried} copper Kronars).\n"
    return wealth, walked, withdrawn


def _refill_run(fake, profile):
    script.probe = SimpleNamespace(ask=fake.ask)
    run = script.Run(fake, dict(PROFILE, **profile), script.parse_args([]))
    run.ring_empty = True
    return run


def _ragge(wealth):
    return [
        ("wealth", wealth),
        ("order ordinary lockpick", RAGGE_QUOTE),
        ("offer 125", RAGGE_BOUGHT),
        ("put my lockpick on my ring", ON_RING),
    ]


def test_an_empty_ring_is_refilled_at_ragges_with_the_profiles_count(monkeypatch):
    wealth, walked, withdrawn = _refill_world(monkeypatch)
    fake = Fake(_ragge(wealth))
    run = _refill_run(fake, {"lockpick_ring": "ring", "lockpick_refill": 3})
    assert script.refill_ring(run)
    assert walked == [{19125}]
    assert withdrawn == []
    assert fake.sent.count("order ordinary lockpick") == 3
    assert fake.sent.count("offer 125") == 3
    assert fake.sent.count("put my lockpick on my ring") == 3
    assert not run.ring_empty
    assert "the ring refilled — 3 ordinary lockpick(s)" in "\n".join(fake.echoed)
    assert not script.refill_ring(run)  # once a run


def test_a_short_purse_fetches_the_picks_price_from_the_teller(monkeypatch):
    # 2026-09-26: 1234 carried against 1250 for ten — "withdrawing 1
    # bronze and 6 copper Kronars".
    wealth, _, withdrawn = _refill_world(monkeypatch, carried=100)
    fake = Fake(_ragge(wealth))
    run = _refill_run(fake, {"lockpick_ring": "ring", "lockpick_refill": 2})
    assert script.refill_ring(run)
    assert withdrawn == [150]  # 250 for two, 100 carried


def test_a_refill_of_zero_never_buys(monkeypatch):
    _refill_world(monkeypatch)
    fake = Fake([])
    run = _refill_run(fake, {"lockpick_ring": "ring", "lockpick_refill": 0})
    assert not script.refill_ring(run)
    assert fake.sent == []


def test_an_order_ragge_refuses_buys_nothing(monkeypatch):
    # 2026-09-26: ORDER 1 answered this — his catalog has no numbers.
    wealth, _, _ = _refill_world(monkeypatch)
    fake = Fake(
        [
            ("wealth", wealth),
            (
                "order ordinary lockpick",
                'Ragge scratches his ear.  "I don\'t believe that I sell that."\n',
            ),
        ]
    )
    run = _refill_run(fake, {"lockpick_ring": "ring", "lockpick_refill": 2})
    assert not script.refill_ring(run)
    assert not any(command.startswith("offer") for command in fake.sent)
    assert run.ring_empty
