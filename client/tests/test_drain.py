"""How fast a pool drains — these tests are the manual.

A skill drops a fixed number of mindstate buckets every 200-second
pulse until it clears: 1.14 for a primary skill, 0.91 for a secondary
one, 0.65 for a tertiary one (fitted from ;xp's rows, #300). The tier
is the guild's skillset placement, except a tertiary skill under 25
ranks drains as secondary. A secondary skill under 50 does not drain as
primary, whatever the wiki says.
"""

import pytest

from client.game import drain


def test_a_paladins_skillsets_place_armor_first_and_magic_last():
    assert drain.placement("Plate Armor", "Paladin") == "primary"
    assert drain.placement("Conviction", "Paladin") == "primary"
    assert drain.placement("Small Edged", "Paladin") == "secondary"
    assert drain.placement("Performance", "Paladin") == "secondary"
    assert drain.placement("Holy Magic", "Paladin") == "tertiary"
    assert drain.placement("Athletics", "Paladin") == "tertiary"


def test_placement_reads_the_guild_table_for_every_guild():
    assert drain.placement("Lunar Magic", "Moon Mage") == "primary"
    assert drain.placement("Plate Armor", "Moon Mage") == "tertiary"
    assert drain.placement("Thievery", "thief") == "primary"
    assert drain.placement("Athletics", "Commoner") == "secondary"


def test_an_unknown_skill_or_guild_has_no_placement():
    assert drain.placement("Basket Weaving", "Paladin") is None
    assert drain.placement("Athletics", "Pirate") is None
    assert drain.placement("Athletics", None) is None


def test_a_tertiary_skill_under_25_ranks_drains_as_secondary():
    assert drain.drain_tier("Athletics", 24, "Paladin") == "secondary"
    assert drain.drain_tier("Athletics", 25, "Paladin") == "tertiary"


def test_a_secondary_skill_under_50_ranks_still_drains_as_secondary():
    # 104 runs of a Paladin's weapon and lore skills under 50 drained at
    # 0.93 buckets a pulse, the secondary rate — not the primary 1.14
    # the Experience page's exception would give (#300).
    assert drain.drain_tier("Small Edged", 30, "Paladin") == "secondary"


def test_minutes_to_a_floor_are_the_buckets_over_the_rate():
    # 24 buckets at 0.65 a pulse: about 36.9 pulses of 200 s.
    assert drain.minutes_to(34, 10, "Athletics", 72, "Paladin") == pytest.approx(
        24 / 0.65 * 200 / 60
    )
    # A mind-locked primary skill clears in about 99 minutes.
    assert drain.minutes_to(34, 0, "Plate Armor", 40, "Paladin") == pytest.approx(
        99.4, abs=0.1
    )


def test_a_skill_already_at_the_floor_takes_no_time():
    assert drain.minutes_to(8, 10, "Athletics", 72, "Paladin") == 0


def test_the_rest_estimate_is_the_slowest_skill():
    experience = {
        "Athletics": {"rank": 72, "mindstate": 30},  # tertiary: 20 buckets
        "Small Edged": {"rank": 41, "mindstate": 34},  # secondary: 24 buckets
        "Performance": {"rank": 61, "mindstate": 5},  # at the floor already
    }
    minutes, skill = drain.rest_estimate(
        experience,
        ["Athletics", "Small Edged", "Performance", "Brawling"],
        10,
        "Paladin",
    )
    assert skill == "Athletics"
    assert minutes == pytest.approx(20 / 0.65 * 200 / 60)


def test_a_rest_with_nothing_to_drain_estimates_nothing():
    experience = {"Athletics": {"rank": 72, "mindstate": 4}}
    assert drain.rest_estimate(experience, ["Athletics"], 10, "Paladin") == (0, None)


def test_a_lowercase_seed_is_not_the_windows_reading():
    # A key in lowercase is a script's seed from before #295, never the
    # exp window's spelling; the estimate reads the window's.
    experience = {"parry ability": {"rank": 44, "mindstate": 11}}
    assert drain.rest_estimate(experience, ["Parry Ability"], 10, "Paladin") == (
        0,
        None,
    )


def test_an_unplaced_guild_gives_no_estimate():
    experience = {"Athletics": {"rank": 72, "mindstate": 30}}
    assert drain.rest_estimate(experience, ["Athletics"], 10, None) is None


def test_wisdom_15_is_the_fitted_rate():
    assert drain.wisdom_factor(15) == pytest.approx(1.0)
    assert drain.wisdom_factor(None) == 1.0


def test_a_wiser_character_drains_faster_by_the_gms_table():
    # GM Armifer's figures: Wisdom 30 pulses at 112% of Wisdom 10's.
    # Against the fitted Wisdom of 15 (103%): 1.12 / 1.03.
    assert drain.wisdom_factor(30) == pytest.approx(1.12 / 1.03)
    assert drain.wisdom_factor(200) == pytest.approx(1.30 / 1.03)
    fitted = drain.minutes_to(34, 10, "Athletics", 72, "Paladin", 15)
    wiser = drain.minutes_to(34, 10, "Athletics", 72, "Paladin", 60)
    assert wiser == pytest.approx(fitted * 1.03 / 1.21)


def test_intelligence_is_not_an_input():
    # Intelligence sizes the pool, and a bucket is a share of the pool,
    # so a rest's length in buckets does not depend on it (#300).
    import inspect

    assert "intelligence" not in inspect.signature(drain.minutes_to).parameters


# --- what a bucket is worth (fitted 2026-09-26) ---


def test_a_rank_costs_two_hundred_bits_plus_the_rank():
    assert drain.rank_cost(0) == 200
    assert drain.rank_cost(90) == 290


def test_the_pages_pool_grows_with_rank_placement_and_the_mental_stats():
    # Elanthipedia's worked shape: 1000 bits at rank 0 for a primary
    # skill at Intelligence and Discipline 10, 850 secondary, 700 tertiary.
    assert drain.pool_bits("primary", 0) == 1000
    assert drain.pool_bits("secondary", 0) == 850
    assert drain.pool_bits("tertiary", 0) == 700
    assert drain.pool_bits("primary", 900) == 8500
    # Intelligence 30 scores 120 and Discipline 30 scores 40: 16 % more.
    assert drain.pool_bits("tertiary", 0, 30, 30) == pytest.approx(700 * 1.16)
    assert drain.intelligence_score(60) == 210
    assert drain.discipline_score(60) == 70


def test_a_bucket_holds_k_over_rank_of_the_pages_bucket():
    # The fit: a Paladin's 375 clean drains, ranks 10-100, held about
    # 8.35 / rank of the page's pool / 34 — 3.2 % of a rank per bucket
    # at rank 50 for a primary skill, 1.8 % at 90 tertiary.
    share = drain.bits_per_bucket("primary", 50, 12, 12) / drain.rank_cost(50)
    assert share == pytest.approx(0.036, abs=0.003)
    share = drain.bits_per_bucket("tertiary", 90, 12, 12) / drain.rank_cost(90)
    assert share == pytest.approx(0.016, abs=0.003)
    # The fit held down to rank 2.7; below 3 the rank counts as 3.
    assert drain.bits_per_bucket("tertiary", 0) == pytest.approx(
        drain.BUCKET_K / 3 * drain.pool_bits("tertiary", 0) / 34
    )
    assert drain.bits_per_bucket("tertiary", 1) == pytest.approx(
        drain.BUCKET_K / 3 * drain.pool_bits("tertiary", 1) / 34
    )


def test_ranks_from_a_mindstate_crosses_ranks_at_their_own_cost():
    # A full pool of a primary skill at rank 50 is about a rank.
    assert drain.ranks_from(34, "Small Edged", 50, 0, "Paladin", 15, 15) == (51, 5)
    # A rank-0 tertiary skill: one bucket is worth 28 % of a rank at the
    # floor's scale, so 22 % goes to 50 %.
    assert drain.ranks_from(1, "Warding", 0, 22, "Barbarian", 10, 12) == (0, 50)
    # Rested experience triples it, across the rank.
    assert drain.ranks_from(1, "Warding", 0, 22, "Barbarian", 10, 12, rexp=True) == (
        1,
        8,
    )
    assert drain.ranks_from(5, "Nonsense", 1, 0, "Paladin") is None
