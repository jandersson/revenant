"""The repair shop in words — these tests are the manual. APPRAISE's
condition phrase to a health band, the repairman's answers to a GIVE
and to a ticket, the ticket's own text, and the pieces a run looks at.
The wordings were captured at Catrox's Forge in the Crossing on
2026-09-24 (#307)."""

from client.game import repair

APPRAISE_DENTED = (
    "You estimate that the full plate is a bit safeguarded against damage and "
    "have a few dents and dings.\n"
    "The full plate is made with metal.\n"
    "Roundtime: 8 sec.\n"
)
APPRAISE_PRISTINE = (
    "You guess that the full plate is quite guarded against damage and are in "
    "pristine condition.\nRoundtime: 5 sec.\n"
)
APPRAISE_MINT = (
    "You believe that the steel scimitar is particularly weak against damage "
    "and is practically in mint condition.\nRoundtime: 8 sec.\n"
)
APPRAISE_SACK = (
    "The canvas sack is made with cloth.\nIt appears that the canvas sack can "
    "be worn over the shoulder.\nRoundtime: 5 sec.\n"
)
QUOTE = (
    'Catrox looks over the plate and says, "That will cost 108 Kronars to '
    "repair.  Just give it to me again if you want, and I'll have it ready in 5 "
    'roisaen."\n'
)
SHORT = 'Catrox mutters, "You will need more coin if I am to be repairing that!"\n'
TICKET = (
    "You hand Catrox 108 Kronars and he gives you back a repair ticket.  Catrox "
    'says, "I will complete this work for you in about 5 roisaen.  Please '
    "don't lose this ticket!  You must have it to reclaim your plate.\"\n"
)
PRISTINE = (
    "Catrox shrugs and says, \"There isn't a scratch on that, and I'm not one "
    'to rob you."\n'
)
NOT_YET = (
    'Catrox smiles and says, "Well that isn\'t gonna be done for another 4 roisaen."\n'
)
ALMOST = (
    'Catrox smiles and says, "Well that is almost done, just give me a few more '
    'moments here."\n'
)
RETURNED = "You hand Catrox your ticket and are handed back some light full plate.\n"
LOOK_WAITING = (
    "Looking at the Catrox ticket you see it is for some light full plate.  You "
    "recall that your plate won't be ready for another 4 roisaen.\n"
    "Written at the bottom you see Catrox's Forge, Crossing, Zoluren.\n"
)
LOOK_READY = (
    "Looking at the Catrox ticket you see it is for some light full plate.  You "
    "recall that your plate should be ready by now.\n"
)


def test_the_condition_phrase_reads_as_its_health_band():
    assert repair.condition(APPRAISE_DENTED) == ("a few dents and dings", 51, 60)
    assert repair.condition(APPRAISE_PRISTINE) == ("in pristine condition", 100, 100)
    assert repair.condition(APPRAISE_MINT) == ("practically in mint condition", 91, 99)


def test_an_appraisal_without_a_condition_is_no_piece_of_gear():
    assert repair.condition(APPRAISE_SACK) is None


def test_the_floor_takes_a_band_that_tops_out_at_or_below_it():
    assert repair.needs_repair(("rather scuffed up", 71, 80), 80)
    assert not repair.needs_repair(("in good condition", 81, 90), 80)
    assert repair.needs_repair(repair.condition(APPRAISE_DENTED))
    assert not repair.needs_repair(None)


def test_the_estimate_is_copper_currency_and_roisaen():
    assert repair.classify_give(QUOTE) == {
        "kind": "quote",
        "copper": 108,
        "currency": "Kronars",
        "roisaen": 5,
    }


def test_the_second_give_hands_back_a_ticket():
    assert repair.classify_give(TICKET) == {"kind": "ticket", "roisaen": 5}


def test_a_quick_second_give_without_coin_is_short():
    assert repair.classify_give(SHORT) == {"kind": "short"}


def test_an_unscratched_piece_is_undamaged():
    assert repair.classify_give(PRISTINE) == {"kind": "undamaged"}


def test_an_unknown_answer_is_unknown():
    assert repair.classify_give("Catrox ignores you.\n") == {"kind": "unknown"}


def test_the_ticket_given_back_returns_the_piece():
    assert repair.classify_pickup(RETURNED) == {
        "kind": "returned",
        "item": "some light full plate",
        "noun": "plate",
    }


def test_a_ticket_given_early_says_how_long_to_wait():
    assert repair.classify_pickup(NOT_YET) == {"kind": "wait", "roisaen": 4}
    assert repair.classify_pickup(ALMOST) == {"kind": "wait", "roisaen": 0}


def test_the_ticket_names_its_shop_and_the_wait():
    assert repair.read_ticket(LOOK_WAITING) == {
        "shop": "Catrox",
        "item": "some light full plate",
        "roisaen": 4,
    }
    assert repair.read_ticket(LOOK_READY)["roisaen"] == 0
    assert repair.read_ticket("What were you referring to?\n") is None


def test_a_repairman_is_found_by_name():
    assert repair.shop_room("Catrox") == 19093
    assert repair.shop_room("catrox") == 19093
    assert repair.shop_room("Nobody") is None


def test_the_pieces_are_the_hands_then_everything_worn():
    possessions = [
        {"noun": "plate", "depth": 0, "worn": True},
        {"noun": "pelt", "depth": 1, "worn": False},
        {"noun": "shield", "depth": 0, "worn": True},
    ]
    hands = [{"noun": "scimitar"}, None]
    assert repair.candidates(possessions, hands) == [
        ("scimitar", "held"),
        ("plate", "worn"),
        ("shield", "worn"),
    ]


def test_named_pieces_replace_the_inventory():
    hands = [{"noun": "scimitar"}, None]
    assert repair.candidates([], hands, ["Plate", "scimitar"]) == [
        ("plate", "worn"),
        ("scimitar", "held"),
    ]
