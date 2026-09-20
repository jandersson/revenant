"""The soul model (client/game/soul.py): the readings parsed off the
captured lines, the quest's readiness, the coin per town, the deeds'
timers kept across runs, and ;soul's words."""

import json

from client.game import soul

# Captured 2026-09-18/19 at the Tower of Honor's orb and arch.
RUB_CHALKY = "You rub the orb...\nIt fades to a dull, chalky color.\n"
RUB_WHITE = "You rub the orb...\nIt warms slightly and turns a steady white hue!\n"
ARCH_WHITE = (
    "You step through a gleaming soulstone archway....\n"
    "The archway emits a warm, steady white hue!\n"
)
EXHALE_EMPTY = "You breathe softly on the orb...\nNothing special seems to happen.\n"
EXHALE_FLICKER = (
    "You breathe softly on the orb...\nYou catch the faintest flicker of light.\n"
)


def test_the_state_reads_off_the_orb_and_the_arch_alike():
    assert soul.parse_state(RUB_CHALKY) == 4
    assert soul.parse_state(RUB_WHITE) == 5
    assert soul.parse_state(ARCH_WHITE) == 5
    assert soul.parse_state("It gleams brightly with a pristine luminescence!") == 7
    assert soul.parse_state("It glows with a pure white light.") == 6
    assert soul.parse_state("It is a pallid grey.") == 3
    assert soul.parse_state("cold and lifeless, tainted darkish grey") == 2
    assert soul.parse_state("which simply mirrors the corruption of your soul") == 1
    assert soul.parse_state("You rub the orb...\n") is None


def test_the_pool_reads_the_most_specific_phrase_first():
    assert soul.parse_pool(EXHALE_EMPTY) == 0
    assert soul.parse_pool(EXHALE_FLICKER) == 2
    assert (
        soul.parse_pool(
            "You believe you catch the faintest flicker of light. You might have imagined it."
        )
        == 1
    )
    assert soul.parse_pool("It briefly flickers with an inner light.") == 3
    assert soul.parse_pool("It flickers with an inner light.") == 4
    assert soul.parse_pool("It pulses briefly with an inner light.") == 5
    assert soul.parse_pool("It pulses with an inner light.") == 6
    assert soul.parse_pool("It pulses rapidly with an inner light.") == 7
    assert (
        soul.parse_pool("It brightens with an inner light, which lingers for a moment.")
        == 8
    )
    assert (
        soul.parse_pool(
            "It brightens with an inner light, which lingers for a few moments before returning to its normal state."
        )
        == 9
    )
    assert (
        soul.parse_pool(
            "It brightens with a powerful inner light, which lingers before returning to its normal state."
        )
        == 10
    )
    assert (
        soul.parse_pool(
            "It brightens with a powerful inner light that, somehow, manages to not cast shadows."
        )
        == 11
    )
    assert soul.parse_pool("You breathe softly on the orb...") is None


def test_describe_and_readiness():
    assert soul.describe(5, 2) == "soul: steady white hue (5/7), pool: 2/11"
    assert soul.describe(None, None) == "no reading"
    assert soul.ready_for_quest(7, 11)
    assert not soul.ready_for_quest(7, 10)
    assert not soul.ready_for_quest(5, 11)


def test_the_coin_follows_the_province_and_the_tithe_command_says_it():
    assert soul.currency_for("[Temple of Light, Alcove of Smaragdaus]") == "dokoras"
    assert soul.currency_for("[Paladins' Guild, Foyer]") == "kronars"
    assert soul.currency_for("[Riverhaven, Temple Gate]") == "lirums"
    assert soul.tithe_command("dokoras") == "put 5 silver dokoras in almsbox"


def test_the_crossing_guilds_box_is_put_in_as_box_and_the_others_as_almsbox():
    # Captured 2026-09-20 on Herald Street: "You also see a paladin guard
    # and a steel tithe box." / "To donate: PUT [amount] [coin type]
    # KRONARS IN BOX"; the temple gate lists "the locked almsbox".
    guild = "You also see a paladin guard and a steel tithe box."
    gate = "You also see a town guard, the Longbow Bridge, the locked almsbox and a high granite wall surrounding the temple grounds."
    assert soul.box_noun(guild) == "box"
    assert soul.box_noun(gate) == "almsbox"
    assert soul.box_noun("") == "almsbox"
    assert soul.tithe_command("kronars", "box") == "put 5 silver kronars in box"
    assert {741, 815} <= set(soul.ALMSBOXES)


def test_classify_names_the_first_outcome_whose_phrase_is_there():
    tithed = (
        "You drop 5 silver dokoras into the almsbox and say a soft prayer as the coins clink in.\n"
        "A warm, soothing sensation washes over your soul.\n"
    )
    assert (
        soul.classify(tithed, ("done", soul.TITHED), ("short", soul.TITHE_SHORT))
        == "done"
    )
    soon = (
        "You start to pay respect to Chadatru again when you decide it would be "
        "inappropriate so soon.  You decide to wait awhile longer.\n"
    )
    assert (
        soul.classify(soon, ("done", soul.PRAYER_DONE), ("soon", soul.PRAYER_SOON))
        == "soon"
    )
    assert soul.classify("nothing", ("done", soul.PRAYER_DONE)) is None


def test_the_timers_persist_per_character_and_say_when_a_deed_is_due(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    assert soul.load_timers("Lanival") == {}
    timers = soul.mark({}, "tithe", True, now=1000)
    soul.save_timers("Lanival", timers)
    assert json.loads((tmp_path / "lanival.json").read_text()) == {"tithe": 1000}
    again = soul.load_timers("Lanival")
    assert soul.due(again, "tithe", now=1000 + 3600) == soul.TITHE_SECONDS - 3600
    assert soul.due(again, "tithe", now=1000 + soul.TITHE_SECONDS) == 0
    # A refusal backs off twenty minutes, whatever the deed's own timer says.
    soul.mark(again, "pray", False, now=5000)
    assert soul.due(again, "pray", now=5000) == soul.REFUSED_BACKOFF
    assert soul.due(again, "pray", now=5000 + soul.REFUSED_BACKOFF) == 0
    # The badge's own timer is the wiki's thirty-one minutes.
    soul.mark(again, "badge", True, now=6000)
    assert soul.due(again, "badge", now=6000 + 30 * 60) == 60
    assert soul.parse_args(["badge"])["verb"] == "badge"
    (tmp_path / "sable.json").write_text("{not json")
    assert soul.load_timers("Sable") == {}


def test_parse_args_reads_the_verb_and_the_options():
    assert soul.parse_args([])["verb"] == "read"
    options = soul.parse_args(["quest", "force", "almsbox=13143", "currency=Lirums"])
    assert options["verb"] == "quest" and options["force"]
    assert options["almsbox"] == 13143 and options["currency"] == "lirums"
    assert soul.parse_args(["altar=x"])["altar"] is None
