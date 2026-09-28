"""The rested-experience footer as a model: parsed, described, and
judged burning or not between two readings (#176)."""

from client.game import rested

FOOTER = (
    "Rested EXP Stored: 5:42 hours  Usable This Cycle: 5:42 hours  "
    "Cycle Refreshes: 21 hours"
)


def test_the_footer_parses_to_minutes():
    assert rested.parse_rested(FOOTER) == {
        "stored": 342,
        "usable": 342,
        "refresh": 1260,
    }
    # Captured 2026-09-12 from the exp window: a bank part burnt, the
    # cycle refreshing within the hour, and one with minutes to go.
    assert rested.parse_rested(
        "Rested EXP Stored: 5:16 hours  Usable This Cycle: 5:02 hours  "
        "Cycle Refreshes: 21 minutes"
    ) == {"stored": 316, "usable": 302, "refresh": 21}
    assert rested.parse_rested("            TDPs:  356") is None


def test_burning_is_the_usable_figure_falling():
    full = {"stored": 345, "usable": 331, "refresh": 79}
    less = {"stored": 344, "usable": 330, "refresh": 78}
    assert rested.burning(full, less) is True
    assert rested.burning(less, less) is False
    # The cycle turned over (captured 2026-09-12): usable jumped back up.
    assert rested.burning({"usable": 335}, {"usable": 342}) is False
    assert rested.burning(None, less) is None
    assert rested.burning(less, None) is None
    assert rested.burning({"usable": None}, less) is None


def test_a_burn_holds_between_the_footers_falls_and_ends_after_a_quiet_spell():
    # Westan, 2026-09-26 21:28-21:30 (#346): Usable 292, 291, 291 read
    # 0, 1, 0 minute by minute; the footer falls every 1-10 minutes
    # while the bank burns, so the flag holds STICKY_MINUTES past a fall.
    def at(usable):
        return {"stored": 300, "usable": usable, "refresh": 600}

    burn = rested.Burn()
    assert burn.step(at(292)) is None  # the first reading: nothing to compare
    assert burn.step(at(292)) is False  # held: no fall seen yet
    assert burn.step(at(291)) is True
    flags = [burn.step(at(291)) for _ in range(rested.STICKY_MINUTES)]
    assert flags == [True] * (rested.STICKY_MINUTES - 1) + [False]
    assert burn.step(at(290)) is True  # a fall again
    assert burn.step(None) is None  # a footer unread: unknown, the last kept
    assert burn.step(at(290)) is True
    # Nothing usable left: whatever fell before, nothing burns now.
    assert burn.step(at(0)) is False
    assert burn.step(at(0)) is False


def test_the_footer_describes_itself_in_hours_and_minutes():
    assert rested.hhmm(342) == "5:42" and rested.hhmm(0) == "0:00"
    assert rested.hhmm(None) == "-"
    assert (
        rested.describe({"stored": 342, "usable": 302, "refresh": 21})
        == "Rested EXP  stored 5:42  usable 5:02  refreshes in 0:21"
    )
