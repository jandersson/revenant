"""How user highlights load and match — these tests are the manual.

Rules come from ~/.revenant/highlights.json (REVENANT_HIGHLIGHTS
overrides); patterns are regexes and only the matched span colors.
Bad entries are skipped; overlaps resolve earliest-match-wins.
"""

import json

from client.highlights import load_rules, spans


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
    rules = load_rules()
    assert len(rules) == 1
    assert rules[0]["regex"].pattern == "good"
    assert rules[0]["bold"] is True


def test_unreadable_file_means_no_rules(monkeypatch, tmp_path):
    path = tmp_path / "highlights.json"
    path.write_text("{not json")
    monkeypatch.setenv("REVENANT_HIGHLIGHTS", str(path))
    assert load_rules() == []


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
