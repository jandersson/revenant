"""The session's command policy for outside senders (#161) — these
tests are the manual: read-only verbs pass, the giving, dropping,
spending and leaving verbs are refused with a reason, DROP allows the
junk list only, PUT only into the character's own container, a
valuable is refused whatever the verb, and the character's file
adjusts the built-ins."""

import json

from client.engine import policy


def _verdicts(*lines, pol=None):
    return [policy.decide(line, pol) for line in lines]


def test_read_only_verbs_pass_and_ordinary_ones_pass_too():
    read, look, walk, stance = _verdicts(
        "INFO", "look at rat", "north", "stance set 100 80 0"
    )
    assert read.allowed and read.tier == "read-only"
    assert look.allowed and look.tier == "read-only"
    assert walk.allowed and walk.tier == "allowed"
    assert stance.allowed


def test_the_giving_spending_and_leaving_verbs_are_refused_with_a_reason():
    for line, word in [
        ("give my handaxe to Sable", "GIVE"),
        ("sell my bundle", "SELL"),
        ("withdraw 10 gold", "WITHDRAW"),
        ("train agility", "TRAIN"),
        ("quit", "QUIT"),
        ("depart", "DEPART"),
        ("exchange 1 gold for lirums", "EXCHANGE"),
        ("discard my armet", "DISCARD"),
        (";reexec", ";reexec"),
    ]:
        verdict = policy.decide(line)
        assert not verdict.allowed and verdict.tier == "denied", line
        assert word in verdict.reason, line


def test_drop_allows_the_junk_list_only(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SETTINGS", str(tmp_path / "settings.json"))
    assert policy.decide("drop my grass rope").allowed
    assert policy.decide("drop grass").allowed
    refused = policy.decide("drop my handaxe")
    assert not refused.allowed and "junk list" in refused.reason
    assert not policy.decide("drop").allowed


def test_put_goes_into_your_own_container_only():
    assert policy.decide("put my pelt in my sack").allowed
    assert policy.decide("put pelt in my bundle").allowed
    refused = policy.decide("put my handaxe in bin")
    assert not refused.allowed and "own container" in refused.reason
    assert not policy.decide("put my coins in Sable's pouch").allowed


def test_a_valuable_is_refused_whatever_the_verb():
    pol = policy.Policy(valuables=("handaxe", "canvas sack"))
    refused = policy.decide("put my handaxe in my sack", pol)  # even into our own
    assert not refused.allowed and "handaxe is a valuable" in refused.reason
    assert not policy.decide("toss my canvas sack", pol).allowed
    assert policy.decide("stow my handaxe", pol).allowed  # STOW keeps it
    assert policy.decide("wear my handaxe", pol).allowed


def test_the_characters_file_adjusts_the_built_ins(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_POLICIES", str(tmp_path))
    (tmp_path / "lanival.json").write_text(
        json.dumps(
            {
                "deny": ["climb"],
                "allow": ["withdraw"],
                "patterns": ["^stance set"],
                "valuables": ["armet"],
            }
        )
    )
    pol = policy.load_policy("Lanival")
    assert not policy.decide("climb oak", pol).allowed
    assert policy.decide("withdraw 1 silver", pol).allowed
    refused = policy.decide("stance set 100 80 0", pol)
    assert not refused.allowed and "policy file" in refused.reason
    assert not policy.decide("give my armet to Sable", pol).allowed
    # No file, a broken file: the built-ins stand.
    assert not policy.decide("quit", policy.load_policy("Uthmor")).allowed
    (tmp_path / "sable.json").write_text("{not json")
    assert policy.load_policy("Sable").denied == policy.DENIED


def test_the_policy_file_lives_beside_the_profiles_by_character(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_POLICIES", str(tmp_path))
    assert policy.policy_path("Lanival") == tmp_path / "lanival.json"
    assert policy.policy_path("") == tmp_path / "default.json"
