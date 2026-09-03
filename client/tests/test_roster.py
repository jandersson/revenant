"""Who the roster sweep visits: cached characters minus the snapshotted.

The rule these pin down (#111): a character is "pending" when a cached
roster names it and xp.db's character table does not. Names are matched
case-insensitively — the game's own capitalisation is what lands in the
database, while a roster may hold anything.
"""

from client.roster import cached_characters, pending_characters, snapshot_summary

DEFAULTS = {
    "account": "second",
    "character": "Fallanor",
    "accounts": {
        "first": {"account": "first", "characters": ["Alvin", "Claude", "Crannach"]},
        "second": {"account": "second", "characters": ["Fallanor", "Westan"]},
    },
}


class TestCachedCharacters:
    def test_every_roster_in_a_stable_order(self):
        # Accounts sorted by name; each roster keeps its own order.
        assert cached_characters(DEFAULTS) == [
            ("first", "Alvin"),
            ("first", "Claude"),
            ("first", "Crannach"),
            ("second", "Fallanor"),
            ("second", "Westan"),
        ]

    def test_the_legacy_flat_cache_still_reads(self):
        # Written before per-account rosters existed: one pair, no
        # "accounts" key at all.
        assert cached_characters({"account": "solo", "character": "Alvin"}) == [
            ("solo", "Alvin")
        ]

    def test_an_empty_cache_yields_nothing(self):
        assert cached_characters({}) == []
        assert cached_characters({"accounts": {}}) == []

    def test_an_account_key_stands_in_for_a_missing_account_name(self):
        defaults = {"accounts": {"keyname": {"characters": ["Doc"]}}}
        assert cached_characters(defaults) == [("keyname", "Doc")]


class TestPendingCharacters:
    def test_snapshotted_characters_drop_out(self):
        assert pending_characters(DEFAULTS, ["Alvin", "Fallanor"]) == [
            ("first", "Claude"),
            ("first", "Crannach"),
            ("second", "Westan"),
        ]

    def test_matching_ignores_case(self):
        # xp.db holds the game's capitalisation; the roster may differ.
        assert pending_characters(DEFAULTS, ["ALVIN", "cRaNnAcH"]) == [
            ("first", "Claude"),
            ("second", "Fallanor"),
            ("second", "Westan"),
        ]

    def test_nothing_snapshotted_means_everyone_is_pending(self):
        assert pending_characters(DEFAULTS, []) == cached_characters(DEFAULTS)

    def test_a_snapshot_for_an_uncached_character_changes_nothing(self):
        # A character snapshotted from another machine, absent here.
        assert pending_characters(DEFAULTS, ["Stranger"]) == cached_characters(DEFAULTS)


class TestSnapshotSummary:
    def test_counts_total_done_and_pending(self):
        assert snapshot_summary(DEFAULTS, ["Alvin", "Fallanor"]) == (5, 2, 3)

    def test_a_full_roster_reports_nothing_pending(self):
        names = [name for _, name in cached_characters(DEFAULTS)]
        assert snapshot_summary(DEFAULTS, names) == (5, 5, 0)

    def test_an_empty_cache_is_all_zeroes(self):
        assert snapshot_summary({}, []) == (0, 0, 0)
