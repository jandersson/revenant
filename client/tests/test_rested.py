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


def test_an_empty_bank_ends_the_burn_at_once_whatever_usable_says():
    # Usable can exceed the bank (Cecil, 2026-09-30: stored 19, usable
    # 118): the bank runs dry first, both figures stop falling, and the
    # burn ends there — not STICKY_MINUTES later.
    burn = rested.Burn()
    burn.step({"stored": 2, "usable": 101, "refresh": 900})
    assert burn.step({"stored": 1, "usable": 100, "refresh": 899}) is True
    assert burn.step({"stored": 0, "usable": 99, "refresh": 898}) is False
    assert burn.step({"stored": 0, "usable": 99, "refresh": 897}) is False


def test_a_sparse_reading_says_what_is_certain_for_as_long_as_it_can():
    # The bank spends at most a minute a minute, so 326 usable minutes
    # are still some 325 minutes on; past that it may have run out.
    reading = {"stored": 326, "usable": 326, "refresh": 1221}
    assert rested.available(reading, 0) is True
    assert rested.available(reading, 325) is True
    assert rested.available(reading, 326) is None
    empty = {"stored": 0, "usable": 0, "refresh": 90}
    assert rested.available(empty, 60) is False  # none until the cycle refreshes
    assert rested.available(empty, 90) is None  # it has refreshed since
    assert rested.available(None, 5) is None
    # Usable can exceed the bank (Cecil, 2026-09-28: 0 stored, 360
    # usable): the lesser is what is left, and an empty bank refills
    # after five minutes without draining.
    unbanked = {"stored": 0, "usable": 360, "refresh": 1313}
    assert rested.available(unbanked, 2) is False
    assert rested.available(unbanked, 5) is None
    assert rested.available({"stored": 25, "usable": 62, "refresh": 71}, 30) is None


def test_a_spent_cycle_reads_none_as_zero():
    # Captured 2026-09-13; unread (NULL) in 1909 rows until 2026-09-29.
    assert rested.parse_rested(
        "Rested EXP Stored: 26 minutes  Usable This Cycle: none  "
        "Cycle Refreshes: 1:26 hour"
    ) == {"stored": 26, "usable": 0, "refresh": 86}


def test_a_minute_is_flagged_from_the_window_or_else_the_last_exp_answer():
    # The window's footer, read every pulse: the Burn rules (#346).
    minute = rested.Minute()
    at = lambda usable: {"stored": 360, "usable": usable, "refresh": 900}  # noqa: E731
    assert minute.step(at(300), now=0) is True  # first minute: the reading's age
    assert minute.step(at(299), now=1) is True
    # An account whose window stays empty: the ;sheet EXP ALL at login
    # (count 1), then nothing new for hours.
    minute = rested.Minute()
    reading = {"stored": 326, "usable": 326, "refresh": 1221}
    flags = [
        minute.step(reading, now=t, window=False, count=1) for t in (0, 60, 325, 326)
    ]
    assert flags == [True, True, True, None]
    # A fresh EXP answer, the same figures or not, dates the reading anew.
    assert minute.step(reading, now=327, window=False, count=2) is True
    # Pools empty: nothing drains, so nothing burns.
    assert minute.step(reading, now=328, window=False, draining=False, count=2) is False


def test_the_footer_describes_itself_in_hours_and_minutes():
    assert rested.hhmm(342) == "5:42" and rested.hhmm(0) == "0:00"
    assert rested.hhmm(None) == "-"
    assert (
        rested.describe({"stored": 342, "usable": 302, "refresh": 21})
        == "Rested EXP  stored 5:42  usable 5:02  refreshes in 0:21"
    )
