"""An Empath's healing in words — these tests are the manual. TOUCH's
listing into wounds, the order they are taken in, the TAKE command for
each, and the self-heal casts off HEALTH. Captured 2026-09-26, the
synthetic Uthmor (an Empath) healing Lanival."""

from client.game.empathy import (
    Injury,
    heal_casts,
    parse_touch,
    take_command,
    transfer_order,
)
from client.game.wounds import parse_health

TOUCH_LISTING = (
    "Lanival's injuries include...\n"
    "Wounds to the NECK:\n"
    "  Fresh External:  light scratches -- negligible\n"
    "  Scars External:  slight discoloration -- negligible\n"
    "  Fresh Internal:  slightly tender -- negligible\n"
    "Wounds to the LEFT ARM:\n"
    "  Fresh External:  cuts and bruises about the left arm -- minor\n"
    "  Scars External:  slight discoloration -- insignificant\n"
    "  Fresh Internal:  minor swelling and bruising around the left arm -- minor\n"
    "Wounds to the RIGHT HAND:\n"
    "  Fresh External:  light scratches -- insignificant\n"
    "Wounds to the CHEST:\n"
    "  Fresh External:  cuts and bruises about the chest area -- minor\n"
    "  Scars External:  slight discoloration -- negligible\n"
    "Wounds to the ABDOMEN:\n"
    "  Scars Internal:  minor internal scarring -- negligible\n"
    "Wounds to the SKIN:\n"
    "  Fresh Internal:  some minor twitching -- minor\n"
    "\n"
    "Lanival has normal vitality.\n"
)
TOUCH_CLEAN = (
    "Lanival's injuries include...\n... no injuries to speak of.\n\n"
    "Lanival has normal vitality.\n"
)


def test_the_listing_becomes_wounds_by_part_kind_and_severity():
    injuries = parse_touch(TOUCH_LISTING)
    assert (
        Injury("left arm", "external", 3, "cuts and bruises about the left arm")
        in injuries
    )
    assert Injury("abdomen", "internal_scar", 2, "minor internal scarring") in injuries
    assert Injury("skin", "internal", 3, "some minor twitching") in injuries
    assert len(injuries) == 11


def test_a_clean_patient_is_an_empty_list_and_no_listing_is_none():
    assert parse_touch(TOUCH_CLEAN) == []
    assert parse_touch("You touch Lanival.\n") is None


def test_the_most_urgent_goes_first_torso_before_limbs_fresh_before_scars():
    order = transfer_order(parse_touch(TOUCH_LISTING))
    firsts = [(i.part, i.kind) for i in order[:5]]
    assert firsts == [
        ("chest", "external"),  # minor, a vital part
        ("skin", "internal"),  # minor, vital, the inside after the outside
        ("left arm", "external"),  # minor, a limb
        ("left arm", "internal"),
        ("neck", "external"),  # negligible, vital, fresh
    ]
    assert order[-1] == Injury(
        "left arm", "scar", 1, "slight discoloration"
    )  # insignificant scars last


def test_bleeding_goes_before_everything():
    injuries = [
        Injury("left leg", "external", 6, "severe"),
        Injury("right arm", "external", 2, "bleeding lightly", bleeding=True),
    ]
    assert transfer_order(injuries)[0].part == "right arm"


def test_each_kind_has_its_take_command():
    assert (
        take_command("Lanival", Injury("chest", "external", 3)) == "take lanival chest"
    )
    assert (
        take_command("Lanival", Injury("left arm", "internal", 3))
        == "take lanival left arm internal"
    )
    assert (
        take_command("Lanival", Injury("neck", "scar", 2)) == "take lanival neck scar"
    )
    assert (
        take_command("Lanival", Injury("abdomen", "internal_scar", 2))
        == "take lanival abdomen internal scar"
    )


def test_the_self_heal_casts_worst_first_wounds_before_scars():
    # Uthmor's HEALTH after taking Lanival's wounds, 2026-09-26 (trimmed).
    health = parse_health(
        "Your body feels at full strength.\n"
        "You have some tiny scratches to the neck, minor scarring along the neck, "
        "minor swelling and bruising around the left arm compounded by cuts and "
        "bruises about the left arm, an occasional twitching in the left arm, "
        "some minor abrasions to the right hand, some minor twitching.\n"
    )
    casts = heal_casts(health)
    assert casts[0] == ("hw", "skin internal")  # minor, vital, only inside
    assert ("hw", "left arm") in casts
    assert ("hs", "left arm internal") in casts
    assert ("hs", "neck") in casts
    assert casts.index(("hw", "left arm")) < casts.index(("hs", "left arm internal"))


def test_an_unhurt_empath_casts_nothing():
    assert heal_casts(parse_health("You have no significant injuries.\n")) == []
