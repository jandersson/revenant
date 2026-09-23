"""The box model ;boxes reads — these tests are the manual. An IDENTIFY
answer reads as one of seventeen ranks, each rank earns a caution or
none, a container listing yields its boxes, and the outcome tables
classify DISARM, PICK and OPEN the way pick.lic's lists do (#293)."""

from client.game.boxes import (
    DISARM_OUTCOMES,
    LOCK_CAUTION,
    LOCK_READINGS,
    OPEN_OUTCOMES,
    PICK_OUTCOMES,
    TAKE_OUTCOMES,
    TOO_HARD,
    TRAP_CAUTION,
    TRAP_READINGS,
    boxes_in,
    caution,
    listed,
    parse_args,
    reading,
)
from client.game.probe import classify

# The wiki's Locksmithing table, verbatim rows (the readings are
# uncaptured on this side, 2026-09-23).
GRANDMOTHER = "An aged grandmother could defeat this trap in her sleep.\n"
SIMPLE_TRAP = "The dented iron box will be a simple matter for you to disarm.\n"
EDGE_TRAP = (
    "The trap has the edge on you, but you've got a good shot at disarming "
    "the dented iron box.\n"
)
LONGSHOT_TRAP = "Disarming the dented iron box would be a longshot.\n"
FLAMES = (
    "A pitiful snowball encased in the Flames of Ushnish would fare better than you.\n"
)
JUNK_LOCK = (
    "The lock is a trivially constructed piece of junk barely worth your time.\n"
)
LEVEL_LOCK = "You think this lock is precisely at your skill level.\n"
PRAYER_LOCK = (
    "Prayer would be a good start for any attempt of yours at picking open "
    "the dented iron box.\n"
)


def test_the_seventeen_readings_rank_one_to_seventeen():
    assert reading(GRANDMOTHER, TRAP_READINGS) == 1
    assert reading(SIMPLE_TRAP, TRAP_READINGS) == 4
    assert reading(EDGE_TRAP, TRAP_READINGS) == 8
    assert reading(LONGSHOT_TRAP, TRAP_READINGS) == 11
    assert reading(FLAMES, TRAP_READINGS) == 17
    assert reading(JUNK_LOCK, LOCK_READINGS) == 3
    assert reading(LEVEL_LOCK, LOCK_READINGS) == 7
    assert reading(PRAYER_LOCK, LOCK_READINGS) == 12
    assert reading("You find nothing of interest.", TRAP_READINGS) is None
    assert reading("", LOCK_READINGS) is None


def test_every_wiki_row_reads_as_its_own_rank():
    # The fragments must not shadow each other: rank n's fragment reads
    # as n and nothing earlier.
    for readings in (TRAP_READINGS, LOCK_READINGS):
        for rank, fragment in enumerate(readings, 1):
            assert reading(f"The box: {fragment}!", readings) == rank


def test_the_caution_follows_the_reading_and_a_longshot_is_too_hard():
    assert caution(1, TRAP_CAUTION) == "quick"
    assert caution(2, TRAP_CAUTION) == "quick"
    assert caution(3, TRAP_CAUTION) == ""
    assert caution(5, TRAP_CAUTION) == ""
    assert caution(6, TRAP_CAUTION) == "careful"
    assert caution(10, TRAP_CAUTION) == "careful"
    assert caution(TOO_HARD, TRAP_CAUTION) is None
    assert caution(17, TRAP_CAUTION) is None
    assert caution(None, TRAP_CAUTION) is None
    assert caution(4, LOCK_CAUTION) == "quick"
    assert caution(5, LOCK_CAUTION) == ""
    assert caution(7, LOCK_CAUTION) == ""
    assert caution(8, LOCK_CAUTION) == "careful"
    assert caution(11, LOCK_CAUTION) is None


def test_a_container_listing_yields_its_boxes_in_order_repeats_kept():
    # LOOK IN MY SACK's shape, captured 2026-09-21 (#269), with boxes.
    answer = (
        "In the canvas sack you see a dented iron box, some bundling rope, "
        "a mildewy deobar crate, a cotton rag, a dented iron box and "
        "a sturdy ironwood strongbox.\n"
    )
    assert boxes_in(answer) == ["box", "crate", "box", "strongbox"]
    assert boxes_in("In the canvas sack you see a cotton rag.\n") == []
    assert boxes_in("There is nothing in there.\n") == []
    assert boxes_in("What were you referring to?\n") is None


def test_a_box_listing_yields_its_items():
    assert listed("In the iron box you see some coins, a ruby and a dagger.\n") == [
        "some coins",
        "a ruby",
        "a dagger",
    ]
    assert listed("In the iron box you see a ruby.\n") == ["a ruby"]
    assert listed("There is nothing in there.\n") == []
    assert listed("It is locked.\n") is None


def test_disarm_answers_classify_a_sprung_trap_before_anything_else():
    sprung = (
        "You carefully work at the trap.\nA stream of corrosive acid sprays "
        "out from the lock and burns your hand!\n"
    )
    assert classify(sprung, DISARM_OUTCOMES) == "sprung"
    assert classify(
        "You're in no shape to be disarming anything.", DISARM_OUTCOMES
    ) == ("injured")
    assert classify(
        "Your examination of the dented iron box fails to reveal to you what "
        "type of trap protects it.",
        DISARM_OUTCOMES,
    ) == ("identify failed")
    assert classify(
        "You work with the trap for a while but are unable to make any progress.",
        DISARM_OUTCOMES,
    ) == ("retry")
    assert classify(
        "Looking closely you see a bent needle sticks harmlessly out of the lock.",
        DISARM_OUTCOMES,
    ) == ("no trap")
    assert classify(
        "You carefully bend the head of the needle so that it can no longer spring.",
        DISARM_OUTCOMES,
    ) == ("disarmed")
    assert classify(SIMPLE_TRAP, DISARM_OUTCOMES) is None


def test_pick_answers_classify_the_lock_and_the_pick():
    opened = "With a satisfying click you remove your lockpick and open and remove the lock.\n"
    assert classify(opened, PICK_OUTCOMES) == "unlocked"
    assert classify("It's not even locked, why bother?", PICK_OUTCOMES) == "not locked"
    assert classify("You discover another lock protecting the box.", PICK_OUTCOMES) == (
        "more locks"
    )
    assert classify("Find a more appropriate tool and try again.", PICK_OUTCOMES) == (
        "wrong pick"
    )
    assert classify("You'd better have an empty hand first.", PICK_OUTCOMES) == (
        "free hand"
    )
    assert classify(
        "Your attempt fails to teach you anything about the lock guarding it.",
        PICK_OUTCOMES,
    ) == ("retry")
    assert classify("Pick what?", PICK_OUTCOMES) == "lost"
    assert classify(LEVEL_LOCK, PICK_OUTCOMES) is None


def test_open_and_take_answers():
    assert classify("It is locked.", OPEN_OUTCOMES) == "locked"
    assert classify("In the iron box you see a ruby.", OPEN_OUTCOMES) == "open"
    assert classify("That is already open.", OPEN_OUTCOMES) == "open"
    assert classify("You pick up 12 copper Kronars.", TAKE_OUTCOMES) == "coins"
    assert classify("You get a ruby from inside your iron box.", TAKE_OUTCOMES) == (
        "taken"
    )
    assert classify("What were you referring to?", TAKE_OUTCOMES) == "gone"


def test_the_arguments():
    assert parse_args([]) == {
        "source": "",
        "until": 34,
        "once": False,
        "careful": False,
        "stand": False,
        "limit": 0,
        "practice": True,
    }
    options = parse_args(
        ["source=backpack", "until=30", "once", "careful", "stand", "limit=3"]
    )
    assert options == {
        "source": "backpack",
        "until": 30,
        "once": True,
        "careful": True,
        "stand": True,
        "limit": 3,
        "practice": True,
    }
    assert parse_args(["nopractice"])["practice"] is False
    assert parse_args(["until=99"])["until"] == 34
    assert parse_args(["until=x", "limit=y"])["limit"] == 0


# Captured 2026-09-23 in the Chambers: the first live run, two grendel
# boxes at Locksmithing 1 — both past the reading, every IDENTIFY taught.
CAPTURED_FAILED = (
    "Your armor hinders your attempt.\nYour brass knuckles hinders your attempt.\n"
    "Careful probing of the oaken crate fails to reveal to you what type of trap "
    "protects it.\nYou get the distinct feeling your careless examination caused "
    "something to shift inside the trap mechanism.  This is not likely to be a "
    "good thing.\nRoundtime: 8 sec.\n"
)
CAPTURED_PRAYER = (
    "Your armor hinders your attempt.\nYour brass knuckles hinders your attempt.\n"
    "While checking the crate with a careful eye, you notice a lumpy green rune "
    "hidden inside the box near the lock.\nPrayer would be a good start for any "
    "attempt of yours at disarming the oaken crate.\nRoundtime: 10 sec.\n"
)
CAPTURED_MINIMAL = (
    "While checking the coffer with a careful eye, you notice a lumpy green rune "
    "hidden inside the box near the lock.\nYou have an amazingly minimal chance at "
    "disarming the steel coffer.\nRoundtime: 8 sec.\n"
)
CAPTURED_RETRY = (
    "You carefully work at disarming the coffer.\nThe lack of identification of the "
    "trap hinders your initial efforts somewhat.\nYour armor hinders your attempt.\n"
    "Your brass knuckles hinders your attempt.\nYou work with the trap for a while "
    "but are unable to make any progress.\nRoundtime: 12 sec.\n"
)


def test_the_first_live_runs_answers_read_as_the_tables_say():
    from client.game.boxes import HINDERED

    assert classify(CAPTURED_FAILED, DISARM_OUTCOMES) == "identify failed"
    assert reading(CAPTURED_FAILED, TRAP_READINGS) is None
    assert reading(CAPTURED_PRAYER, TRAP_READINGS) == 12
    assert caution(12, TRAP_CAUTION) is None  # past 11: too hard
    assert reading(CAPTURED_MINIMAL, TRAP_READINGS) == 13
    assert classify(CAPTURED_RETRY, DISARM_OUTCOMES) == "retry"
    assert classify(CAPTURED_PRAYER, DISARM_OUTCOMES) is None  # a reading, no outcome
    assert any(word in CAPTURED_PRAYER.lower() for word in HINDERED)
    assert not any(word in CAPTURED_MINIMAL.lower() for word in HINDERED)
