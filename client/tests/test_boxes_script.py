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
    out = run(fake, ["nopractice"])
    assert "get crate from my sack" in fake.sent
    assert "disarm my crate identify" in fake.sent
    assert "disarm my crate careful" not in fake.sent
    assert "put my crate in my sack" in fake.sent
    assert "the crate's trap reads 11/17 — past 11, too hard" in out
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
    run(fake, ["nopractice"])  # the ordinal is the point, not the practice
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


class Practising(Fake):
    """A handle whose Locksmithing mindstate also steps on every DISARM
    IDENTIFY — the practice on a too-hard box teaches (2026-09-23)."""

    def ask(self, s, command, *_):
        answer = super().ask(s, command)
        if command.endswith("identify") and self.mindstates:
            self.state.experience["Locksmithing"]["mindstate"] = self.mindstates.pop(0)
        return answer


def test_a_box_past_the_reading_is_practised_on_until_the_target():
    # The first live run (2026-09-23): both boxes read 12/17 and 13/17
    # and went straight back, yet the identifies had taught 0 -> 2/34.
    # Practice keeps identifying the box until Locksmithing reaches the
    # target, then puts it back.
    answers = [
        ("look in my sack", "In the canvas sack you see a mildewy deobar crate.\n"),
        (
            "get crate from my sack",
            "You get a mildewy deobar crate from inside your canvas sack.\n",
        ),
        ("disarm my crate identify", LONGSHOT),
        ("put my crate in my sack", "You put your crate in your canvas sack.\n"),
    ]
    fake = Practising(answers, mindstates=[1, 11, 20, 30, 34, 34, 34])
    out = run(fake, ["once"])
    identifies = fake.sent.count("disarm my crate identify")
    assert identifies >= 4  # the reading, then the practice rounds
    assert "disarm my crate careful" not in fake.sent
    assert "the crate is past the reading — practising on it (identify)" in out
    assert (
        "the crate goes back into the sack — practised on, for a better locksmith"
        in out
    )
    assert "Locksmithing at 34/34 — done" in out


def test_nopractice_puts_a_box_past_the_reading_straight_back():
    answers = [
        ("look in my sack", "In the canvas sack you see a mildewy deobar crate.\n"),
        (
            "get crate from my sack",
            "You get a mildewy deobar crate from inside your canvas sack.\n",
        ),
        ("disarm my crate identify", LONGSHOT),
        ("put my crate in my sack", "You put your crate in your canvas sack.\n"),
    ]
    fake = Practising(answers, mindstates=[1, 11, 20])
    out = run(fake, ["nopractice"])
    assert fake.sent.count("disarm my crate identify") == 1
    assert "practising" not in out
    assert "every box tried — 0 opened, 1 kept, 0 identify(ies) practised" in out
