"""What gates the next circle: guild requirements computed from ranks.

Every guild's circle requirements are a fixed table (Elanthipedia), so
revenant computes the gate list locally from the character sheet the
same way the guildleader does — ``;circle`` (scripts/circle.py) and
beholder's circle view read the latest ;sheet snapshot and report what
to train, with have/need ranks. All eleven circled guilds are encoded;
docs/circles.md records the tables' evidence, the wiki corrections
applied, and the open anomalies. A captured Thief ASK <guildleader>
ABOUT CIRCLE validates the computation gate for gate.

Model: a requirement is either a named skill (Thievery, Parry Ability,
Inner Fire, ...) or a slot ("3rd Survival" = your third-best survival
skill). Ranks required to advance TO circle C sum the per-circle rates
across the table's circle bands up to C. Slots fill best-first by
(rank, percent); a guild's named skills don't also fill its slots
unless the wiki marks them soft (Thief's Thievery/Stealth, Bard's
Tactics, ...).
"""

# Circle bands shared by every guild's table: 1-10, 11-30, 31-70,
# 71-100, 101-150, 151+.
BAND_TOPS = (10, 30, 70, 100, 150)

# Which skills can fill each set's slots. Named-requirement skills are
# excluded per guild at computation time (unless soft); Parry Ability
# and Expertise never fill weapon slots, the Masteries have their own
# "mastery" slot (Barbarian's Primary Mastery), and armor slots draw
# from the armor proper — Defending/Shield Usage/Conviction appear
# only as named requirements. The Primary Magic skills (Holy, Lunar,
# Arcane, Life, Elemental Magic; Inner Fire; Inner Magic) are absent
# from the magic set on purpose: Elanthipedia's guild pages list them
# among the "mastery" skills that never count toward Nth requirements,
# and name the slot fillers — Attunement, Arcana, Targeted Magic,
# Augmentation, Debilitation, Utility, Warding (#134). docs/circles.md
# records the assumptions and the evidence.
SLOT_SKILLS = {
    "survival": (
        "Athletics",
        "Backstab",
        "Evasion",
        "First Aid",
        "Instinct",
        "Locksmithing",
        "Outdoorsmanship",
        "Perception",
        "Skinning",
        "Stealth",
        "Thanatology",
        "Thievery",
    ),
    "weapon": (
        "Bow",
        "Brawling",
        "Crossbow",
        "Heavy Thrown",
        "Large Blunt",
        "Large Edged",
        "Light Thrown",
        # Offhand Weapon is a mastery skill: "never count toward Nth
        # skill requirements" (Cleric and Moon Mage pages, #148).
        "Polearms",
        "Slings",
        "Small Blunt",
        "Small Edged",
        "Staves",
        "Twohanded Blunt",
        "Twohanded Edged",
    ),
    "mastery": ("Melee Mastery", "Missile Mastery"),
    "lore": (
        "Alchemy",
        "Appraisal",
        "Empathy",
        "Enchanting",
        "Engineering",
        "Forging",
        "Mechanical Lore",
        "Outfitting",
        "Performance",
        "Scholarship",
        "Tactics",
        "Trading",
    ),
    "armor": ("Light Armor", "Heavy Armor"),
    "magic": (
        "Arcana",
        "Astrology",
        "Attunement",
        "Augmentation",
        "Debilitation",
        "Sorcery",
        "Summoning",
        "Targeted Magic",
        "Theurgy",
        "Utility",
        "Warding",
    ),
}

# One guild's table: requirement rows in wiki order, each
# (category, kind, which, per-band rates). kind "named" checks the
# skill itself; kind "slot" checks the n-th best of a SLOT_SKILLS set.
# "soft" names may fill slots too; "magic_word" is the guildleader's
# phrasing for magic slots. Transcribed from each guild's Elanthipedia
# Circle Requirements table — corrections in docs/circles.md.
GUILDS = {
    "Barbarian": {
        "soft": (),
        "magic_word": "Supernatural",
        "requirements": (
            ("weapon", "named", "Expertise", (4, 5, 5, 5, 6, 15)),
            ("weapon", "slot", ("mastery", 1), (4, 5, 6, 6, 6, 15)),
            ("weapon", "named", "Parry Ability", (4, 4, 4, 4, 5, 13)),
            ("weapon", "slot", ("weapon", 1), (4, 5, 6, 6, 6, 15)),
            ("weapon", "slot", ("weapon", 2), (4, 5, 6, 6, 6, 15)),
            ("weapon", "slot", ("weapon", 3), (2, 3, 3, 4, 5, 13)),
            ("weapon", "slot", ("weapon", 4), (1, 2, 2, 3, 4, 10)),
            ("armor", "slot", ("armor", 1), (3, 4, 4, 5, 6, 13)),
            # Band 11-30 reads 2 on the wiki's rate table; three
            # cumulative checkpoints prove 1.
            ("armor", "slot", ("armor", 2), (1, 1, 2, 3, 4, 10)),
            ("survival", "named", "Evasion", (3, 4, 4, 5, 6, 15)),
            ("survival", "slot", ("survival", 1), (2, 2, 3, 3, 3, 8)),
            ("survival", "slot", ("survival", 2), (2, 2, 3, 3, 3, 8)),
            # Bands 31-70 read 2 on the wiki's rate table for both
            # these slots; the cumulative checkpoints prove 1.5.
            ("survival", "slot", ("survival", 3), (2, 2, 1.5, 3, 3, 8)),
            ("survival", "slot", ("survival", 4), (1, 1, 1.5, 2, 2, 5)),
            ("lore", "named", "Tactics", (1, 1, 2, 2, 3, 8)),
            ("lore", "slot", ("lore", 1), (1, 1, 2, 2, 3, 8)),
            ("magic", "named", "Inner Fire", (1, 2, 3, 3, 3, 8)),
            ("magic", "slot", ("magic", 1), (1, 2, 2, 3, 3, 8)),
            ("magic", "slot", ("magic", 2), (0, 0, 2, 2, 3, 8)),
        ),
    },
    "Bard": {
        "soft": ("Tactics",),
        "magic_word": "Magic",
        "requirements": (
            ("armor", "slot", ("armor", 1), (2, 2, 2, 3, 3, 8)),
            ("weapon", "named", "Parry Ability", (2, 3, 3, 4, 5, 13)),
            ("weapon", "slot", ("weapon", 1), (3, 3, 4, 4, 5, 13)),
            ("weapon", "slot", ("weapon", 2), (2, 3, 3, 4, 4, 10)),
            ("lore", "named", "Performance", (4, 4, 5, 5, 6, 15)),
            ("lore", "named", "Tactics", (2, 3, 3, 4, 5, 13)),
            ("lore", "slot", ("lore", 1), (3, 3, 4, 4, 5, 13)),
            ("lore", "slot", ("lore", 2), (3, 3, 3, 4, 5, 13)),
            ("lore", "slot", ("lore", 3), (2, 2, 3, 3, 4, 10)),
            ("magic", "slot", ("magic", 1), (3, 3, 4, 4, 5, 13)),
            ("magic", "slot", ("magic", 2), (2, 2, 3, 4, 5, 13)),
            ("magic", "slot", ("magic", 3), (2, 2, 3, 3, 4, 10)),
            ("magic", "slot", ("magic", 4), (1, 2, 2, 3, 4, 10)),
            ("magic", "slot", ("magic", 5), (0, 0, 2, 3, 3, 8)),
            ("survival", "slot", ("survival", 1), (1, 2, 2, 3, 4, 10)),
            ("survival", "slot", ("survival", 2), (1, 1, 2, 2, 3, 8)),
            ("survival", "slot", ("survival", 3), (1, 1, 1, 2, 2, 5)),
            ("survival", "slot", ("survival", 4), (1, 1, 1, 2, 2, 5)),
        ),
    },
    "Cleric": {
        "soft": ("Attunement",),
        # "For Clerics, Sorcery and Thievery also do not count towards
        # Nth skill requirements" (Elanthipedia Cleric page, #148).
        "excluded": ("Sorcery", "Thievery"),
        "magic_word": "Magic",
        "requirements": (
            ("armor", "named", "Shield Usage", (1, 2, 2, 3, 4, 10)),
            ("armor", "slot", ("armor", 1), (2, 2, 3, 3, 4, 10)),
            ("weapon", "named", "Parry Ability", (2, 3, 3, 3, 4, 10)),
            ("weapon", "slot", ("weapon", 1), (3, 3, 4, 4, 5, 13)),
            ("weapon", "slot", ("weapon", 2), (0, 0, 2, 2, 3, 8)),
            ("lore", "slot", ("lore", 1), (2, 3, 3, 4, 5, 13)),
            ("lore", "slot", ("lore", 2), (2, 2, 3, 3, 4, 10)),
            ("lore", "slot", ("lore", 3), (1, 2, 2, 3, 3, 10)),
            ("lore", "slot", ("lore", 4), (0, 0, 2, 3, 3, 8)),
            ("magic", "named", "Theurgy", (3, 4, 4, 5, 6, 15)),
            ("magic", "named", "Attunement", (2, 2, 3, 3, 4, 10)),
            ("magic", "slot", ("magic", 1), (4, 4, 5, 5, 6, 15)),
            ("magic", "slot", ("magic", 2), (4, 4, 4, 5, 6, 15)),
            # Band 31-70 reads 4 on the wiki's rate table; three
            # cumulative checkpoints prove 3.
            ("magic", "slot", ("magic", 3), (3, 3, 3, 4, 5, 13)),
            ("magic", "slot", ("magic", 4), (0, 3, 3, 4, 5, 13)),
            ("magic", "slot", ("magic", 5), (0, 0, 3, 4, 5, 13)),
            ("survival", "slot", ("survival", 1), (1, 2, 2, 3, 3, 8)),
            ("survival", "slot", ("survival", 2), (1, 1, 2, 2, 3, 8)),
            ("survival", "slot", ("survival", 3), (1, 1, 1, 2, 2, 5)),
            ("survival", "slot", ("survival", 4), (1, 1, 1, 2, 2, 5)),
        ),
    },
    "Empath": {
        "soft": ("Outdoorsmanship",),
        "magic_word": "Magic",
        "requirements": (
            ("lore", "named", "Empathy", (4, 5, 6, 6, 7, 15)),
            ("lore", "named", "Scholarship", (3, 3, 4, 5, 5, 13)),
            ("lore", "slot", ("lore", 1), (3, 3, 4, 4, 5, 13)),
            ("lore", "slot", ("lore", 2), (2, 3, 3, 4, 4, 10)),
            ("lore", "slot", ("lore", 3), (2, 2, 3, 3, 4, 10)),
            ("magic", "slot", ("magic", 1), (3, 3, 4, 4, 5, 13)),
            ("magic", "slot", ("magic", 2), (2, 3, 3, 4, 5, 13)),
            ("magic", "slot", ("magic", 3), (2, 3, 3, 4, 4, 10)),
            ("magic", "slot", ("magic", 4), (0, 2, 3, 3, 4, 10)),
            ("magic", "slot", ("magic", 5), (0, 0, 3, 3, 4, 10)),
            ("survival", "named", "First Aid", (2, 3, 3, 3, 4, 10)),
            ("survival", "named", "Outdoorsmanship", (1, 1, 2, 2, 2, 5)),
            ("survival", "slot", ("survival", 1), (1, 2, 2, 3, 4, 10)),
            ("survival", "slot", ("survival", 2), (1, 2, 2, 3, 4, 10)),
            ("survival", "slot", ("survival", 3), (1, 1, 2, 3, 3, 8)),
        ),
    },
    "Moon Mage": {
        "soft": (),
        # "For Moon Mages, Thievery also does not count towards Nth
        # skill requirements" (Elanthipedia Moon Mage page, #148).
        "excluded": ("Thievery",),
        "magic_word": "Magic",
        "requirements": (
            ("lore", "named", "Scholarship", (3, 3, 3, 4, 4, 10)),
            ("lore", "slot", ("lore", 1), (2, 3, 3, 4, 5, 13)),
            ("lore", "slot", ("lore", 2), (2, 2, 3, 3, 4, 10)),
            ("lore", "slot", ("lore", 3), (1, 2, 2, 3, 3, 8)),
            ("magic", "named", "Astrology", (3, 4, 4, 5, 6, 15)),
            ("magic", "slot", ("magic", 1), (4, 4, 5, 6, 7, 18)),
            ("magic", "slot", ("magic", 2), (4, 4, 4, 5, 6, 15)),
            ("magic", "slot", ("magic", 3), (3, 4, 4, 5, 5, 13)),
            ("magic", "slot", ("magic", 4), (2, 3, 4, 5, 5, 13)),
            ("magic", "slot", ("magic", 5), (0, 3, 3, 4, 5, 13)),
            ("magic", "slot", ("magic", 6), (0, 3, 3, 4, 5, 13)),
            ("survival", "slot", ("survival", 1), (2, 3, 3, 4, 5, 13)),
            ("survival", "slot", ("survival", 2), (2, 3, 3, 4, 4, 10)),
            ("survival", "slot", ("survival", 3), (2, 2, 3, 3, 4, 10)),
            ("survival", "slot", ("survival", 4), (2, 2, 2, 3, 3, 8)),
            ("survival", "slot", ("survival", 5), (0, 2, 2, 3, 3, 8)),
        ),
    },
    "Necromancer": {
        "soft": ("Targeted Magic",),
        "magic_word": "Magic",
        "requirements": (
            ("survival", "named", "Thanatology", (3, 4, 4, 5, 6, 15)),
            ("survival", "slot", ("survival", 1), (4, 4, 5, 5, 6, 15)),
            ("survival", "slot", ("survival", 2), (4, 4, 5, 5, 6, 15)),
            ("survival", "slot", ("survival", 3), (3, 4, 4, 5, 5, 13)),
            ("survival", "slot", ("survival", 4), (3, 4, 4, 5, 5, 13)),
            ("survival", "slot", ("survival", 5), (3, 4, 4, 5, 5, 13)),
            ("survival", "slot", ("survival", 6), (3, 3, 4, 4, 5, 13)),
            ("survival", "slot", ("survival", 7), (2, 3, 3, 4, 4, 10)),
            ("magic", "named", "Targeted Magic", (2, 2, 3, 4, 5, 13)),
            ("magic", "slot", ("magic", 1), (3, 4, 4, 5, 6, 15)),
            ("magic", "slot", ("magic", 2), (3, 3, 4, 5, 6, 15)),
            ("magic", "slot", ("magic", 3), (2, 3, 3, 4, 5, 13)),
            ("magic", "slot", ("magic", 4), (2, 3, 3, 4, 5, 13)),
            ("magic", "slot", ("magic", 5), (0, 0, 3, 4, 5, 13)),
            ("lore", "slot", ("lore", 1), (2, 2, 3, 3, 3, 8)),
            ("lore", "slot", ("lore", 2), (2, 2, 2, 3, 3, 8)),
            ("weapon", "named", "Small Edged", (1, 2, 2, 2, 2, 5)),
            ("armor", "slot", ("armor", 1), (1, 2, 2, 2, 3, 8)),
        ),
    },
    "Paladin": {
        "soft": ("Shield Usage", "Tactics", "Scholarship"),
        "magic_word": "Magic",
        "requirements": (
            ("armor", "named", "Conviction", (3, 4, 4, 5, 5, 13)),
            ("armor", "named", "Defending", (3, 3, 4, 4, 5, 13)),
            ("armor", "named", "Shield Usage", (2, 2, 3, 3, 4, 10)),
            ("armor", "slot", ("armor", 1), (4, 5, 5, 5, 6, 15)),
            ("armor", "slot", ("armor", 2), (2, 3, 3, 4, 5, 13)),
            ("weapon", "named", "Parry Ability", (3, 3, 4, 4, 5, 13)),
            ("weapon", "slot", ("weapon", 1), (3, 4, 4, 5, 5, 13)),
            ("weapon", "slot", ("weapon", 2), (0, 2, 3, 4, 4, 10)),
            ("lore", "named", "Tactics", (1, 2, 3, 3, 4, 10)),
            ("lore", "named", "Scholarship", (1, 2, 2, 3, 3, 8)),
            ("lore", "slot", ("lore", 1), (2, 3, 3, 4, 4, 10)),
            ("lore", "slot", ("lore", 2), (1, 2, 3, 3, 4, 10)),
            ("lore", "slot", ("lore", 3), (1, 1, 2, 2, 3, 8)),
            ("magic", "slot", ("magic", 1), (1, 2, 2, 3, 3, 8)),
            ("magic", "slot", ("magic", 2), (1, 1, 2, 2, 3, 8)),
            ("magic", "slot", ("magic", 3), (1, 1, 1, 2, 2, 5)),
            ("survival", "named", "Evasion", (2, 3, 3, 4, 4, 10)),
            ("survival", "slot", ("survival", 1), (1, 2, 2, 3, 3, 8)),
            ("survival", "slot", ("survival", 2), (1, 1, 2, 2, 3, 8)),
            ("survival", "slot", ("survival", 3), (1, 1, 1, 2, 2, 5)),
            ("survival", "slot", ("survival", 4), (1, 1, 1, 2, 2, 5)),
        ),
    },
    "Ranger": {
        "soft": ("Instinct",),
        "magic_word": "Magic",
        "requirements": (
            ("survival", "named", "Instinct", (2, 3, 3, 4, 4, 10)),
            ("survival", "slot", ("survival", 1), (4, 4, 4, 5, 6, 15)),
            ("survival", "slot", ("survival", 2), (4, 4, 4, 5, 6, 15)),
            ("survival", "slot", ("survival", 3), (3, 4, 4, 5, 6, 15)),
            ("survival", "slot", ("survival", 4), (3, 4, 4, 4, 5, 13)),
            ("survival", "slot", ("survival", 5), (3, 4, 4, 4, 5, 13)),
            ("survival", "slot", ("survival", 6), (2, 3, 3, 4, 4, 10)),
            ("survival", "slot", ("survival", 7), (2, 3, 3, 4, 4, 10)),
            ("survival", "slot", ("survival", 8), (2, 2, 3, 3, 4, 10)),
            ("weapon", "slot", ("weapon", 1), (3, 3, 4, 4, 5, 13)),
            ("weapon", "slot", ("weapon", 2), (1, 2, 3, 3, 4, 10)),
            ("weapon", "named", "Parry Ability", (2, 2, 2, 3, 3, 8)),
            ("armor", "slot", ("armor", 1), (2, 3, 3, 4, 5, 13)),
            ("armor", "slot", ("armor", 2), (0, 1, 2, 3, 3, 8)),
            ("armor", "named", "Defending", (1, 2, 2, 3, 4, 10)),
            ("magic", "slot", ("magic", 1), (1, 2, 2, 3, 3, 8)),
            ("magic", "slot", ("magic", 2), (1, 2, 2, 3, 3, 8)),
            ("magic", "slot", ("magic", 3), (1, 1, 2, 2, 3, 8)),
            ("lore", "slot", ("lore", 1), (1, 1, 2, 2, 3, 8)),
            ("lore", "slot", ("lore", 2), (0, 1, 1, 2, 2, 5)),
        ),
    },
    "Thief": {
        "soft": ("Thievery", "Stealth"),
        "magic_word": "Supernatural",
        "requirements": (
            ("survival", "named", "Thievery", (2, 3, 3, 4, 4, 10)),
            ("survival", "named", "Stealth", (2, 2, 3, 3, 4, 10)),
            ("survival", "slot", ("survival", 1), (4, 4, 5, 5, 6, 15)),
            ("survival", "slot", ("survival", 2), (4, 4, 4, 5, 6, 15)),
            ("survival", "slot", ("survival", 3), (3, 4, 4, 5, 6, 15)),
            ("survival", "slot", ("survival", 4), (3, 4, 4, 5, 6, 15)),
            ("survival", "slot", ("survival", 5), (3, 4, 4, 4, 5, 13)),
            ("survival", "slot", ("survival", 6), (2, 3, 4, 4, 5, 13)),
            ("survival", "slot", ("survival", 7), (2, 3, 3, 4, 5, 13)),
            ("survival", "slot", ("survival", 8), (1, 2, 2, 3, 3, 8)),
            ("weapon", "named", "Parry Ability", (1, 2, 2, 3, 3, 8)),
            ("weapon", "slot", ("weapon", 1), (3, 3, 4, 4, 5, 13)),
            ("weapon", "slot", ("weapon", 2), (1, 2, 3, 3, 4, 10)),
            ("lore", "slot", ("lore", 1), (1, 2, 3, 3, 4, 10)),
            ("lore", "slot", ("lore", 2), (1, 2, 2, 3, 3, 8)),
            ("lore", "slot", ("lore", 3), (1, 1, 2, 2, 3, 8)),
            ("armor", "slot", ("armor", 1), (2, 2, 2, 3, 3, 8)),
            ("magic", "named", "Inner Magic", (1, 2, 3, 3, 4, 10)),
            ("magic", "slot", ("magic", 1), (1, 2, 2, 3, 3, 10)),
            ("magic", "slot", ("magic", 2), (0, 0, 2, 2, 4, 8)),
        ),
    },
    "Trader": {
        "soft": (),
        "magic_word": "Magic",
        "requirements": (
            ("armor", "slot", ("armor", 1), (2, 3, 3, 3, 4, 10)),
            ("armor", "slot", ("armor", 2), (1, 2, 2, 3, 3, 8)),
            ("weapon", "slot", ("weapon", 1), (1, 2, 2, 3, 3, 8)),
            ("lore", "named", "Trading", (4, 5, 6, 6, 7, 15)),
            ("lore", "named", "Appraisal", (3, 3, 4, 5, 6, 15)),
            ("lore", "slot", ("lore", 1), (3, 3, 4, 4, 5, 13)),
            ("lore", "slot", ("lore", 2), (2, 3, 3, 4, 4, 10)),
            ("lore", "slot", ("lore", 3), (2, 2, 3, 4, 4, 10)),
            ("survival", "slot", ("survival", 1), (3, 3, 4, 4, 5, 13)),
            ("survival", "slot", ("survival", 2), (2, 3, 3, 4, 4, 10)),
            ("survival", "slot", ("survival", 3), (2, 3, 3, 4, 4, 10)),
            ("survival", "slot", ("survival", 4), (1, 2, 2, 3, 4, 10)),
            ("survival", "slot", ("survival", 5), (1, 2, 2, 3, 3, 8)),
            ("survival", "slot", ("survival", 6), (1, 1, 1, 2, 2, 5)),
        ),
    },
    "Warrior Mage": {
        "soft": (),
        "magic_word": "Magic",
        "requirements": (
            ("magic", "named", "Summoning", (3, 4, 5, 5, 5, 13)),
            ("magic", "named", "Targeted Magic", (4, 4, 4, 5, 6, 15)),
            ("magic", "slot", ("magic", 1), (4, 4, 5, 5, 6, 15)),
            ("magic", "slot", ("magic", 2), (4, 4, 4, 5, 6, 15)),
            ("magic", "slot", ("magic", 3), (3, 3, 3, 4, 5, 13)),
            ("magic", "slot", ("magic", 4), (0, 3, 3, 4, 5, 13)),
            ("magic", "slot", ("magic", 5), (0, 0, 3, 4, 5, 13)),
            ("weapon", "named", "Parry Ability", (2, 3, 3, 4, 4, 10)),
            ("weapon", "slot", ("weapon", 1), (3, 4, 4, 5, 5, 13)),
            ("weapon", "slot", ("weapon", 2), (0, 3, 3, 4, 4, 10)),
            ("weapon", "slot", ("weapon", 3), (0, 0, 2, 3, 4, 10)),
            ("lore", "named", "Scholarship", (1, 1, 2, 2, 3, 8)),
            ("lore", "slot", ("lore", 1), (2, 2, 3, 3, 4, 10)),
            ("lore", "slot", ("lore", 2), (2, 2, 2, 3, 3, 8)),
            ("lore", "slot", ("lore", 3), (1, 2, 2, 3, 3, 8)),
            ("armor", "named", "Defending", (1, 1, 2, 2, 3, 8)),
            ("armor", "slot", ("armor", 1), (2, 2, 3, 3, 4, 10)),
            ("survival", "slot", ("survival", 1), (1, 1, 2, 2, 3, 8)),
            ("survival", "slot", ("survival", 2), (1, 1, 2, 2, 3, 8)),
            ("survival", "slot", ("survival", 3), (1, 1, 1, 2, 2, 5)),
            ("survival", "slot", ("survival", 4), (1, 1, 1, 2, 2, 5)),
        ),
    },
}


def required_ranks(rates, circle):
    """Ranks required to hold a circle: the per-circle rate summed
    across bands up to it (matches the tables' Cumulative columns)."""
    total, floor = 0, 0
    for band, rate in zip(BAND_TOPS + (None,), rates):
        top = circle if band is None else min(circle, band)
        if top > floor:
            total += rate * (top - floor)
            floor = top
    return total


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def slot_label(guild, slot_set, n):
    if slot_set == "mastery":
        return "Primary Mastery"
    word = {
        "survival": "Survival",
        "weapon": "Weapon",
        "lore": "Lore",
        "armor": "Armor",
        "magic": GUILDS[guild]["magic_word"],
    }[slot_set]
    return f"{_ordinal(n)} {word}"


# Guilds that exist and have no circles at all — not gaps in the table.
NO_CIRCLES = {"Commoner"}


def explain_no_gates(guild):
    """Why gates() returned None, in words for the user: a guild without
    circles (join one), or a guild the table does not know (#133)."""
    if guild in NO_CIRCLES:
        return (
            f"{guild}s don't circle — join a guild, and ;circle will "
            "report what gates the next one"
        )
    return f"no circle requirements known for guild {guild!r}"


def gates(ranks, circle, guild):
    """The unmet requirements for advancing from `circle` to the next.

    ranks: {skill: (rank, percent)} — a ;sheet snapshot's roster.
    Returns [{category, label, skill, have, need}] in table order, or
    None for a guild without circles (Commoner). Slots fill best-first
    by (rank, percent); equal-rank ties may sit in different slots
    than the game shows, but the same requirements come out unmet
    either way.
    """
    table = GUILDS.get(guild)
    if table is None:
        return None
    named = {
        which
        for _, kind, which, _ in table["requirements"]
        if kind == "named" and which not in table["soft"]
    }
    # A guild's own list of skills that never count toward its Nth
    # requirements, quoted from its wiki page (#148); most pages name
    # only the shared mastery skills, which the slot sets already omit.
    excluded = set(table.get("excluded", ()))
    filled = {}
    for slot_set, candidates in SLOT_SKILLS.items():
        trained = [
            (skill, ranks[skill][0], ranks[skill][1])
            for skill in candidates
            if skill in ranks and skill not in named and skill not in excluded
        ]
        trained.sort(key=lambda entry: (-entry[1], -entry[2], entry[0]))
        filled[slot_set] = trained
    target = circle + 1
    unmet = []
    for category, kind, which, rates in table["requirements"]:
        need = required_ranks(rates, target)
        if not need:
            continue
        if kind == "named":
            label, skill = which, which
            have = ranks.get(which, (0, 0))[0]
        else:
            slot_set, n = which
            label = slot_label(guild, slot_set, n)
            if n <= len(filled[slot_set]):
                skill, have, _ = filled[slot_set][n - 1]
            else:
                skill, have = None, 0  # nothing trained for this slot yet
        if have < need:
            unmet.append(
                {
                    "category": category,
                    "label": label,
                    "skill": skill,
                    "have": have,
                    "need": need,
                }
            )
    return unmet


def describe(unmet, target):
    """;circle's report: one line per knowledge set, guildleader style,
    with have/need ranks."""
    if not unmet:
        return [f"nothing gates circle {target} — go see your guildleader"]
    lines = [f"gates to circle {target}:"]
    for category in ("armor", "weapon", "magic", "survival", "lore"):
        entries = [gate for gate in unmet if gate["category"] == category]
        if not entries:
            continue
        # Slots first, named requirements after — the guildleader's own
        # order ("1st Weapon (Small Edged), Parry").
        entries.sort(key=lambda gate: gate["label"] == gate["skill"])
        parts = []
        for gate in entries:
            name = gate["label"]
            if gate["skill"] and gate["skill"] != gate["label"]:
                name += f" ({gate['skill']})"
            parts.append(f"{name} {gate['have']}/{gate['need']}")
        lines.append(f"  {category}: " + ", ".join(parts))
    return lines
