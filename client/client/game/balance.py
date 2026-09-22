"""The balance words, low to high — the twelve levels Elanthipedia's Combat
page lists and the game states in its combat lines (#280).

A module of its own so the parser (client/engine/xml_data.py, which
reloads only with the session) and the readable view (client/game/
status.py, which reloads with the scripts) share it without the view
importing a name the running engine may not have yet: on 2026-09-22 a
session started before the balance landed failed to reload status.py
("cannot import name 'BALANCE_LEVELS' from 'client.engine.xml_data'")
and kept the old code until relaunched.
"""

BALANCE_LEVELS = (
    "completely imbalanced",
    "hopelessly unbalanced",
    "extremely imbalanced",
    "very badly balanced",
    "badly balanced",
    "somewhat off balance",
    "off balance",
    "slightly off balance",
    "solidly balanced",
    "nimbly balanced",
    "adeptly balanced",
    "incredibly balanced",
)
SOLID = "solidly balanced"  # the base the Combat page names


def level(word):
    """0 (completely imbalanced) to 11 (incredibly balanced), None for a
    word that is not one of the twelve."""
    return BALANCE_LEVELS.index(word) if word in BALANCE_LEVELS else None
