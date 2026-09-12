"""How user highlights load and match — these tests are the manual.

Rules come from ~/.revenant/highlights.json (REVENANT_HIGHLIGHTS
overrides); patterns are regexes and only the matched span colors.
Bad entries are skipped; overlaps resolve earliest-match-wins.
"""

import json

from client.ui.highlights import load_rules, spans


def _rules(*patterns):
    return [
        {"regex": __import__("re").compile(pattern), "color": "#fff", "bold": False}
        for pattern in patterns
    ]


def test_first_load_writes_the_starter_file(monkeypatch, tmp_path):
    path = tmp_path / "highlights.json"
    monkeypatch.setenv("REVENANT_HIGHLIGHTS", str(path))
    rules = load_rules()
    assert path.is_file()
    assert rules, "the starter example should compile"


def test_bad_entries_are_skipped_not_fatal(monkeypatch, tmp_path):
    path = tmp_path / "highlights.json"
    path.write_text(
        json.dumps(
            [
                {"pattern": "good", "color": "#abc", "bold": True},
                {"pattern": "([unclosed", "color": "#abc"},  # bad regex
                {"color": "#abc"},  # no pattern
                "not even an object",
            ]
        )
    )
    monkeypatch.setenv("REVENANT_HIGHLIGHTS", str(path))
    rules = load_rules(defaults=())
    assert len(rules) == 1
    assert rules[0]["regex"].pattern == "good"
    assert rules[0]["bold"] is True


def test_unreadable_file_means_no_rules_of_its_own(monkeypatch, tmp_path):
    path = tmp_path / "highlights.json"
    path.write_text("{not json")
    monkeypatch.setenv("REVENANT_HIGHLIGHTS", str(path))
    assert load_rules(defaults=()) == []
    assert [rule["name"] for rule in load_rules()] == ["balance", "roundtime", "ready"]


# --- the shipped defaults (2026-09-13) ---


def test_the_defaults_soft_highlight_the_balance_roundtime_and_ready_lines(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("REVENANT_HIGHLIGHTS", str(tmp_path / "highlights.json"))
    rules = load_rules()
    by_name = {rule["name"]: rule for rule in rules if rule["name"]}
    assert set(by_name) == {"balance", "roundtime", "ready"}
    assert not any(rule["bold"] for rule in by_name.values())
    line = "[You're solidly balanced and in strong position.]"
    assert spans(line, rules) == [(0, len(line), by_name["balance"])]
    assert spans("[Roundtime 6 sec.]", rules)[0][2] is by_name["roundtime"]
    assert spans("Roundtime: 2 sec.", rules)[0][2] is by_name["roundtime"]
    assert (
        spans("You feel fully prepared to cast your spell.", rules)[0][2]
        is (by_name["ready"])
    )
    assert (
        spans("You feel fully attuned to the mana streams again.", rules)[0][2]
        is (by_name["ready"])
    )
    assert spans("A ship's rat bites at you.", rules) == []


def test_a_file_entry_disables_or_replaces_a_default_by_name(monkeypatch, tmp_path):
    path = tmp_path / "highlights.json"
    path.write_text(
        json.dumps(
            [
                {"disable": "roundtime"},
                {"name": "balance", "pattern": "balanced", "color": "#fff"},
                {"pattern": "rat", "color": "#abc"},
            ]
        )
    )
    monkeypatch.setenv("REVENANT_HIGHLIGHTS", str(path))
    rules = load_rules()
    assert [rule["name"] for rule in rules] == ["balance", None, "ready"]
    assert rules[0]["regex"].pattern == "balanced"  # the file's own balance rule
    assert spans("[Roundtime 6 sec.]", rules) == []


def test_spans_mark_only_the_matches():
    (rule,) = _rules(r"\btroll\b")
    assert spans("a troll arrives; trolls follow", [rule]) == [(2, 7, rule)]


def test_spans_from_several_rules_interleave():
    one, two = _rules("aaa", "bbb")
    result = spans("aaa bbb aaa", [one, two])
    assert [(start, end) for start, end, _ in result] == [(0, 3), (4, 7), (8, 11)]


def test_overlaps_resolve_earliest_match_wins():
    early, late = _rules("gleaming br", "broadsword")
    result = spans("a gleaming broadsword", [early, late])
    assert [(start, end) for start, end, _ in result] == [(2, 13)]


def test_zero_width_matches_are_ignored():
    (rule,) = _rules(r"x*")
    assert spans("abc", [rule]) == []


def test_entries_roundtrip_for_the_editor(monkeypatch, tmp_path):
    path = tmp_path / "highlights.json"
    monkeypatch.setenv("REVENANT_HIGHLIGHTS", str(path))
    from client.ui.highlights import load_entries, save_entries

    entries = [
        {"pattern": "good", "color": "#abc123", "bold": True},
        {"pattern": "([broken", "color": "#abcdef", "bold": False},  # kept raw
    ]
    save_entries(entries)
    assert load_entries() == entries  # broken patterns survive for fixing


def test_pattern_error_names_the_problem():
    from client.ui.highlights import pattern_error

    assert pattern_error(r"\btroll\b") is None
    assert "unterminated" in pattern_error("([broken") or pattern_error("([broken")
