"""How circle gates are computed from the sheet — the manual.

Evidence pinning the model (docs/circles.md): every guild's encoded
rate table re-derives its wiki Cumulative column (checkpoints 10/30/
70/100; Thief through 200), and a captured Thief ASK <guildleader>
ABOUT CIRCLE is reproduced gate for gate from the same character's
captured EXP ALL. Necromancer and Ranger publish no cumulative table,
so their transcriptions carry no cross-check.
"""

from client import circles

# The wiki Cumulative columns, keyed by requirement label. Values are
# ranks required at circles 10/30/70/100 (Thief: also 150/200). Known
# wiki corrections are commented where applied.
WIKI_CUMULATIVE = {
    "Thief": {
        "Thievery": (20, 80, 200, 320, 520, 1020),
        "Stealth": (20, 60, 180, 270, 470, 970),
        "1st Survival": (40, 120, 320, 470, 770, 1520),
        "2nd Survival": (40, 120, 280, 430, 730, 1480),
        "3rd Survival": (30, 110, 270, 420, 720, 1470),
        "4th Survival": (30, 110, 270, 420, 720, 1470),
        "5th Survival": (30, 110, 270, 390, 640, 1290),
        "6th Survival": (20, 80, 240, 360, 610, 1260),
        "7th Survival": (20, 80, 200, 320, 570, 1220),
        "8th Survival": (10, 50, 130, 220, 370, 770),
        "Parry Ability": (10, 50, 130, 220, 370, 770),
        "1st Weapon": (30, 90, 250, 370, 620, 1270),
        "2nd Weapon": (10, 50, 170, 260, 460, 960),
        "1st Lore": (10, 50, 170, 260, 460, 960),
        "2nd Lore": (10, 50, 130, 220, 370, 770),
        "3rd Lore": (10, 30, 110, 170, 320, 720),
        "1st Armor": (20, 60, 140, 230, 380, 780),
        "Inner Magic": (10, 50, 170, 260, 460, 960),
        "1st Supernatural": (10, 50, 130, 220, 370, 870),
        # The wiki reads 130 at circle 100; its own rates and 150
        # value (340 = 140 + 4*50) prove 140.
        "2nd Supernatural": (0, 0, 80, 140, 340, 740),
    },
    "Barbarian": {
        # Expertise checked to circle 70 only: the wiki's cumulative
        # column (440 at 100) contradicts its own band-4 rate (5 →
        # 490) with no clean per-circle rate in between — recorded in
        # docs/circles.md, rates encoded as printed.
        "Expertise": (40, 140, 340),
        "Primary Mastery": (40, 140, 380, 560),
        "Parry Ability": (40, 120, 280, 400),
        "1st Weapon": (40, 140, 380, 560),
        "2nd Weapon": (40, 140, 380, 560),
        "3rd Weapon": (20, 80, 200, 320),
        "4th Weapon": (10, 50, 130, 220),
        "1st Armor": (30, 110, 270, 420),
        "2nd Armor": (10, 30, 110, 200),
        "Evasion": (30, 110, 270, 420),
        "1st Survival": (20, 60, 180, 270),
        "2nd Survival": (20, 60, 180, 270),
        "3rd Survival": (20, 60, 120, 210),
        "4th Survival": (10, 30, 90, 150),
        "Tactics": (10, 30, 110, 170),
        "1st Lore": (10, 30, 110, 170),
        "Inner Fire": (10, 50, 170, 260),
        "1st Supernatural": (10, 50, 130, 220),
        "2nd Supernatural": (0, 0, 80, 140),
    },
    "Bard": {
        "1st Armor": (20, 60, 140, 230),
        "Parry Ability": (20, 80, 200, 320),
        "1st Weapon": (30, 90, 250, 370),
        "2nd Weapon": (20, 80, 200, 320),
        "Performance": (40, 120, 320, 470),
        "Tactics": (20, 80, 200, 320),
        "1st Lore": (30, 90, 250, 370),
        "2nd Lore": (30, 90, 210, 330),
        "3rd Lore": (20, 60, 180, 270),
        "1st Magic": (30, 90, 250, 370),
        "2nd Magic": (20, 60, 180, 300),
        "3rd Magic": (20, 60, 180, 270),
        # 4th Magic checked to circle 70 only: the wiki's cumulative
        # (210 at 100) contradicts its own band-4 rate (3 → 220) with
        # no clean per-circle rate in between — docs/circles.md.
        "4th Magic": (10, 50, 130),
        "5th Magic": (0, 0, 80, 170),
        "1st Survival": (10, 50, 130, 220),
        "2nd Survival": (10, 30, 110, 170),
        "3rd Survival": (10, 30, 70, 130),
        "4th Survival": (10, 30, 70, 130),
    },
    "Cleric": {
        "Shield Usage": (10, 50, 130, 220),
        "1st Armor": (20, 60, 180, 270),
        "Parry Ability": (20, 80, 200, 290),
        "1st Weapon": (30, 90, 250, 370),
        "2nd Weapon": (0, 0, 80, 140),
        "1st Lore": (20, 80, 200, 320),
        "2nd Lore": (20, 60, 180, 270),
        "3rd Lore": (10, 50, 130, 220),
        "4th Lore": (0, 0, 80, 170),
        "Theurgy": (30, 110, 270, 420),
        "Attunement": (20, 60, 180, 270),
        "1st Magic": (40, 120, 320, 470),
        "2nd Magic": (40, 120, 280, 430),
        "3rd Magic": (30, 90, 210, 330),
        "4th Magic": (0, 60, 180, 300),
        "5th Magic": (0, 0, 120, 240),
        "1st Survival": (10, 50, 130, 220),
        "2nd Survival": (10, 30, 110, 170),
        "3rd Survival": (10, 30, 70, 130),
        "4th Survival": (10, 30, 70, 130),
    },
    "Empath": {
        "Empathy": (40, 140, 380, 560),
        "Scholarship": (30, 90, 250, 400),
        "1st Lore": (30, 90, 250, 370),
        "2nd Lore": (20, 80, 200, 320),
        "3rd Lore": (20, 60, 180, 270),
        "1st Magic": (30, 90, 250, 370),
        "2nd Magic": (20, 80, 200, 320),
        "3rd Magic": (20, 80, 200, 320),
        "4th Magic": (0, 40, 160, 250),
        "5th Magic": (0, 0, 120, 210),
        "First Aid": (20, 80, 200, 290),
        "Outdoorsmanship": (10, 30, 110, 170),
        "1st Survival": (10, 50, 130, 220),
        "2nd Survival": (10, 50, 130, 220),
        "3rd Survival": (10, 30, 110, 200),
    },
    "Moon Mage": {
        "Scholarship": (30, 90, 210, 330),
        "1st Lore": (20, 80, 200, 320),
        "2nd Lore": (20, 60, 180, 270),
        "3rd Lore": (10, 50, 130, 220),
        "Astrology": (30, 110, 270, 420),
        "1st Magic": (40, 120, 320, 500),
        "2nd Magic": (40, 120, 280, 430),
        "3rd Magic": (30, 110, 270, 420),
        "4th Magic": (20, 80, 240, 390),
        "5th Magic": (0, 60, 180, 300),
        "6th Magic": (0, 60, 180, 300),
        "1st Survival": (20, 80, 200, 320),
        "2nd Survival": (20, 80, 200, 320),
        "3rd Survival": (20, 60, 180, 270),
        "4th Survival": (20, 60, 140, 230),
        "5th Survival": (0, 40, 120, 210),
    },
    "Paladin": {
        "Conviction": (30, 110, 270, 420),
        "Defending": (30, 90, 250, 370),
        "Shield Usage": (20, 60, 180, 270),
        "1st Armor": (40, 140, 340, 490),
        "2nd Armor": (20, 80, 200, 320),
        "Parry Ability": (30, 90, 250, 370),
        "1st Weapon": (30, 110, 270, 420),
        "2nd Weapon": (0, 40, 160, 280),
        "Tactics": (10, 50, 170, 260),
        "Scholarship": (10, 50, 130, 220),
        "1st Lore": (20, 80, 200, 320),
        "2nd Lore": (10, 50, 170, 260),
        "3rd Lore": (10, 30, 110, 170),
        "1st Magic": (10, 50, 130, 220),
        "2nd Magic": (10, 30, 110, 170),
        "3rd Magic": (10, 30, 70, 130),
        "Evasion": (20, 80, 200, 320),
        "1st Survival": (10, 50, 130, 220),
        "2nd Survival": (10, 30, 110, 170),
        "3rd Survival": (10, 30, 70, 130),
        "4th Survival": (10, 30, 70, 130),
    },
    "Trader": {
        "1st Armor": (20, 80, 200, 290),
        "2nd Armor": (10, 50, 130, 220),
        "1st Weapon": (10, 50, 130, 220),
        "Trading": (40, 140, 380, 560),
        "Appraisal": (30, 90, 250, 400),
        "1st Lore": (30, 90, 250, 370),
        "2nd Lore": (20, 80, 200, 320),
        "3rd Lore": (20, 60, 180, 300),
        "1st Survival": (30, 90, 250, 370),
        "2nd Survival": (20, 80, 200, 320),
        "3rd Survival": (20, 80, 200, 320),
        "4th Survival": (10, 50, 130, 220),
        "5th Survival": (10, 50, 130, 220),
        "6th Survival": (10, 30, 70, 130),
    },
    "Warrior Mage": {
        "Summoning": (30, 110, 310, 460),
        "Targeted Magic": (40, 120, 280, 430),
        "1st Magic": (40, 120, 320, 470),
        "2nd Magic": (40, 120, 280, 430),
        "3rd Magic": (30, 90, 210, 330),
        "4th Magic": (0, 60, 180, 300),
        "5th Magic": (0, 0, 120, 240),
        "Parry Ability": (20, 80, 200, 320),
        "1st Weapon": (30, 110, 270, 420),
        "2nd Weapon": (0, 60, 180, 300),
        "3rd Weapon": (0, 0, 80, 170),
        "Scholarship": (10, 30, 110, 170),
        "1st Lore": (20, 60, 180, 270),
        "2nd Lore": (20, 60, 140, 230),
        "3rd Lore": (10, 50, 130, 220),
        "Defending": (10, 30, 110, 170),
        "1st Armor": (20, 60, 180, 270),
        "1st Survival": (10, 30, 110, 170),
        "2nd Survival": (10, 30, 110, 170),
        "3rd Survival": (10, 30, 70, 130),
        "4th Survival": (10, 30, 70, 130),
    },
}

CHECKPOINTS = (10, 30, 70, 100, 150, 200)

# Captured EXP ALL (2026-08-22), the roster behind the guildleader
# validation below: {skill: (rank, percent)}.
ROSTER = {
    "Light Armor": (3, 48),
    "Defending": (2, 69),
    "Parry Ability": (1, 64),
    "Small Edged": (3, 0),
    "Crossbow": (2, 0),
    "Brawling": (2, 89),
    "Melee Mastery": (2, 29),
    "Missile Mastery": (1, 0),
    "Inner Magic": (1, 0),
    "Augmentation": (1, 0),
    "Evasion": (3, 73),
    "Athletics": (22, 37),
    "Perception": (3, 0),
    "Stealth": (4, 0),
    "Locksmithing": (4, 0),
    "Thievery": (3, 0),
    "First Aid": (1, 0),
    "Backstab": (2, 0),
    "Scholarship": (1, 0),
    "Mechanical Lore": (3, 0),
    "Appraisal": (1, 32),
    "Tactics": (1, 28),
}


def _labelled_rates(guild):
    """{label: rates} for one guild's encoded requirement rows."""
    rows = {}
    for category, kind, which, rates in circles.GUILDS[guild]["requirements"]:
        if kind == "named":
            rows[which] = rates
        else:
            rows[circles.slot_label(guild, *which)] = rates
    return rows


def test_every_guild_rebuilds_its_wiki_cumulative_column():
    for guild, expected_rows in WIKI_CUMULATIVE.items():
        encoded = _labelled_rates(guild)
        # The fixture and the encoding must cover the same rows.
        assert set(encoded) == set(expected_rows), guild
        for label, expected in expected_rows.items():
            computed = tuple(
                circles.required_ranks(encoded[label], circle)
                for circle in CHECKPOINTS[: len(expected)]
            )
            assert computed == expected, (guild, label)


def test_guilds_without_cumulative_tables_are_still_encoded():
    # Necromancer and Ranger publish no cumulative column — their
    # transcriptions exist but carry no cross-check (docs/circles.md).
    for guild in ("Necromancer", "Ranger"):
        assert circles.GUILDS[guild]["requirements"]
    assert set(circles.GUILDS) == set(WIKI_CUMULATIVE) | {"Necromancer", "Ranger"}


def test_required_ranks_inside_a_band():
    # Circle 15: ten circles of the 1-10 rate, five of the 11-30 rate.
    thief = _labelled_rates("Thief")
    assert circles.required_ranks(thief["1st Survival"], 15) == 4 * 10 + 4 * 5


def test_gates_reproduce_the_guildleaders_answer():
    # Captured ASK KALAG ABOUT CIRCLE for this roster at circle 1:
    #   armor:    1st Armor (Light Armor)
    #   weapon:   1st Weapon (Small Edged), Parry
    #   magic:    1st Supernatural (Augmentation), Inner Magic
    #   survival: 2nd..8th Survival slots, Thievery
    #   lore:     3rd Lore (Scholarship)
    # The computation reproduces every gate, with two documented
    # deviations (docs/circles.md): equal-rank ties may occupy
    # different slots than the game shows (Stealth/Locksmithing at 4,
    # the 1-rank lores), and 2nd Lore is reported unmet here though
    # the guildleader stayed silent about it — the one open anomaly
    # between the wiki table and the captured answer.
    unmet = circles.gates(ROSTER, circle=1, guild="Thief")
    assert [
        (gate["label"], gate["skill"], gate["have"], gate["need"]) for gate in unmet
    ] == [
        ("Thievery", "Thievery", 3, 4),
        ("2nd Survival", "Locksmithing", 4, 8),
        ("3rd Survival", "Stealth", 4, 6),
        ("4th Survival", "Evasion", 3, 6),
        ("5th Survival", "Perception", 3, 6),
        ("6th Survival", "Thievery", 3, 4),
        ("7th Survival", "Backstab", 2, 4),
        ("8th Survival", "First Aid", 1, 2),
        ("Parry Ability", "Parry Ability", 1, 2),
        ("1st Weapon", "Small Edged", 3, 6),
        ("2nd Lore", "Appraisal", 1, 2),
        ("3rd Lore", "Tactics", 1, 2),
        ("1st Armor", "Light Armor", 3, 4),
        ("Inner Magic", "Inner Magic", 1, 2),
        ("1st Supernatural", "Augmentation", 1, 2),
    ]


def test_soft_requirements_fill_survival_slots():
    # Stealth both meets its named requirement and occupies a survival
    # slot — the wiki's "soft requirement" footnote.
    ranks = {"Stealth": (100, 0), "Thievery": (90, 0)}
    unmet = circles.gates(ranks, circle=1, guild="Thief")
    survival = [gate for gate in unmet if gate["label"].endswith("Survival")]
    assert [gate["label"] for gate in survival] == [
        f"{n}rd Survival" if n == 3 else f"{n}th Survival" for n in range(3, 9)
    ]
    assert all(gate["skill"] is None for gate in survival)  # slots 3+ empty
    assert not any(gate["label"] == "Stealth" for gate in unmet)


def test_named_requirements_stay_out_of_slots_unless_soft():
    # A Bard's Performance (named, not soft) never fills a lore slot;
    # their Tactics (named AND soft) does.
    ranks = {"Performance": (50, 0), "Tactics": (4, 0)}
    unmet = circles.gates(ranks, circle=1, guild="Bard")
    first_lore = next(gate for gate in unmet if gate["label"] == "1st Lore")
    assert first_lore["skill"] == "Tactics"
    assert first_lore["have"] == 4


def test_barbarians_primary_mastery_is_the_better_mastery():
    ranks = {"Melee Mastery": (3, 0), "Missile Mastery": (7, 10)}
    unmet = circles.gates(ranks, circle=1, guild="Barbarian")
    mastery = next(gate for gate in unmet if gate["label"] == "Primary Mastery")
    assert mastery["skill"] == "Missile Mastery"
    assert mastery["have"] == 7


def test_a_guild_without_circles_returns_none():
    assert circles.gates({}, circle=0, guild="Commoner") is None


def test_an_untrained_slot_reports_no_skill():
    unmet = circles.gates({}, circle=1, guild="Thief")
    first_weapon = next(gate for gate in unmet if gate["label"] == "1st Weapon")
    assert first_weapon["skill"] is None
    assert first_weapon["have"] == 0


def test_describe_reports_per_knowledge_set():
    lines = circles.describe(circles.gates(ROSTER, circle=1, guild="Thief"), target=2)
    assert lines[0] == "gates to circle 2:"
    assert "  armor: 1st Armor (Light Armor) 3/4" in lines
    assert any(
        line.startswith("  weapon: 1st Weapon (Small Edged) 3/6, Parry Ability 1/2")
        for line in lines
    )
    assert circles.describe([], target=2) == [
        "nothing gates circle 2 — go see your guildleader"
    ]
