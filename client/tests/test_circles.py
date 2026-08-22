"""How circle gates are computed from the sheet — the manual.

Two evidence sources pin the model (docs/circles.md): Elanthipedia's
Thief requirement table (the Cumulative column re-derived here from
the encoded rates), and a captured ASK <guildleader> ABOUT CIRCLE
reproduced gate for gate from the same character's captured EXP ALL.
"""

from client import circles

# Elanthipedia's Cumulative column: ranks required at circles
# 10/30/70/100/150/200. One cell corrected: 2nd Magic at 100 reads 130
# on the wiki, but its own rates and its 150 value (340 = 140 + 4*50)
# prove 140 — a wiki typo, not a model choice.
WIKI_CUMULATIVE = {
    ("named", "Thievery"): (20, 80, 200, 320, 520, 1020),
    ("named", "Stealth"): (20, 60, 180, 270, 470, 970),
    ("survival", 1): (40, 120, 320, 470, 770, 1520),
    ("survival", 2): (40, 120, 280, 430, 730, 1480),
    ("survival", 3): (30, 110, 270, 420, 720, 1470),
    ("survival", 4): (30, 110, 270, 420, 720, 1470),
    ("survival", 5): (30, 110, 270, 390, 640, 1290),
    ("survival", 6): (20, 80, 240, 360, 610, 1260),
    ("survival", 7): (20, 80, 200, 320, 570, 1220),
    ("survival", 8): (10, 50, 130, 220, 370, 770),
    ("named", "Parry Ability"): (10, 50, 130, 220, 370, 770),
    ("weapon", 1): (30, 90, 250, 370, 620, 1270),
    ("weapon", 2): (10, 50, 170, 260, 460, 960),
    ("lore", 1): (10, 50, 170, 260, 460, 960),
    ("lore", 2): (10, 50, 130, 220, 370, 770),
    ("lore", 3): (10, 30, 110, 170, 320, 720),
    ("armor", 1): (20, 60, 140, 230, 380, 780),
    ("named", "Inner Magic"): (10, 50, 170, 260, 460, 960),
    ("magic", 1): (10, 50, 130, 220, 370, 870),
    ("magic", 2): (0, 0, 80, 140, 340, 740),
}

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


def test_encoded_rates_rebuild_the_wiki_cumulative_column():
    for key, expected in WIKI_CUMULATIVE.items():
        rates = circles.THIEF_REQUIREMENTS[key]
        computed = tuple(
            circles.required_ranks(rates, circle)
            for circle in (10, 30, 70, 100, 150, 200)
        )
        assert computed == expected, key


def test_required_ranks_inside_a_band():
    # Circle 15: ten circles of the 1-10 rate, five of the 11-30 rate.
    assert circles.required_ranks(circles.THIEF_REQUIREMENTS[("survival", 1)], 15) == (
        4 * 10 + 4 * 5
    )


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
    unmet = circles.gates(ROSTER, circle=1)
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
    unmet = circles.gates(ranks, circle=1)
    survival = [gate for gate in unmet if gate["label"].endswith("Survival")]
    assert [gate["label"] for gate in survival] == [
        f"{n}rd Survival" if n == 3 else f"{n}th Survival" for n in range(3, 9)
    ]
    assert all(gate["skill"] is None for gate in survival)  # slots 3+ empty
    assert not any(gate["label"] == "Stealth" for gate in unmet)


def test_an_untrained_slot_reports_no_skill():
    unmet = circles.gates({}, circle=1)
    first_weapon = next(gate for gate in unmet if gate["label"] == "1st Weapon")
    assert first_weapon["skill"] is None
    assert first_weapon["have"] == 0


def test_describe_reports_per_knowledge_set():
    lines = circles.describe(circles.gates(ROSTER, circle=1), target=2)
    assert lines[0] == "gates to circle 2:"
    assert "  armor: 1st Armor (Light Armor) 3/4" in lines
    assert any(
        line.startswith("  weapon: 1st Weapon (Small Edged) 3/6, Parry Ability 1/2")
        for line in lines
    )
    assert circles.describe([], target=2) == [
        "nothing gates circle 2 — go see your guildleader"
    ]
