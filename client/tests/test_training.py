"""The training plan and the decisions ;train makes from it — the manual.

A plan file per character, coerced on load so a hand edit cannot break
the loop; a task is done at its target mindstate, the cycle is done
when no task is left to run, the rest is over when every trained
skill has drained, and the safe rooms rotate.
"""

import json

import pytest

from client import training
from client.training import (
    DEFAULTS,
    describe,
    load_plan,
    next_task,
    normalize,
    plan_path,
    rested,
    safe_room,
    satisfied,
    save_plan,
    starter_plan,
    status_lines,
    tracked_skills,
    validate,
)


@pytest.fixture(autouse=True)
def plans_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path / "training"))
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path / "profiles"))
    return tmp_path / "training"


def plan(**overrides):
    values = dict(DEFAULTS)
    values["tasks"] = [
        {"name": "climbs", "script": "athletics", "skills": ["Athletics"]},
        {
            "name": "rats",
            "script": "hunt",
            "skills": ["Small Edged", "Evasion"],
            "stop_word": "stop",
        },
        {"name": "music", "commands": ["play my flute"], "skills": ["Performance"]},
    ]
    values.update(overrides)
    return normalize(values)


def exp(**mindstates):
    return {
        skill.replace("_", " "): {"rank": 5, "percent": 0, "mindstate": state}
        for skill, state in mindstates.items()
    }


# -- the file ---------------------------------------------------------------


def test_the_plan_file_is_per_character_under_the_training_dir(plans_dir):
    assert plan_path("Lanival") == plans_dir / "lanival.json"
    assert plan_path("Sable's Twin!") == plans_dir / "sablestwin.json"


def test_a_missing_plan_is_the_defaults():
    assert load_plan("Lanival") == DEFAULTS


def test_a_saved_plan_round_trips_and_a_hand_edit_is_coerced(plans_dir):
    save_plan("Lanival", plan(target=32))
    assert load_plan("Lanival")["target"] == 32
    text = json.loads((plans_dir / "lanival.json").read_text())
    text["target"] = "31"  # a string from a hand edit
    text["safe_rooms"] = "home, bank"  # comma-separated shorthand
    text["tasks"][0]["skills"] = "Athletics"
    text["tasks"][0]["minutes"] = ""
    (plans_dir / "lanival.json").write_text(json.dumps(text))
    loaded = load_plan("Lanival")
    assert loaded["target"] == 31
    assert loaded["safe_rooms"] == ["home", "bank"]
    assert loaded["tasks"][0]["skills"] == ["Athletics"]
    assert loaded["tasks"][0]["minutes"] is None


def test_a_broken_plan_file_is_the_defaults(plans_dir):
    plans_dir.mkdir()
    (plans_dir / "lanival.json").write_text("{not json")
    assert load_plan("Lanival") == DEFAULTS


def test_tasks_get_every_key_and_a_name():
    loaded = normalize({"tasks": [{"script": "athletics"}, {"commands": ["hum"]}]})
    first, second = loaded["tasks"]
    assert first["name"] == "athletics" and first["skills"] == []
    assert first["stop_grace"] == 120 and first["target"] is None
    assert second["name"] == "task2" and second["pace"] == 5


def test_unknown_keys_survive_for_a_newer_build():
    loaded = normalize({"future": 1, "tasks": [{"script": "x", "later": True}]})
    assert loaded["future"] == 1
    assert loaded["tasks"][0]["later"] is True


def test_the_starter_plan_takes_home_and_skills_from_the_profile(monkeypatch):
    from client.profile import save_profile

    save_profile("Lanival", {"home": "town green", "train_skills": ["Small Edged"]})
    starter = starter_plan("Lanival")
    assert starter["safe_rooms"] == ["town green"]
    assert [task["script"] for task in starter["tasks"]] == ["athletics", "hunt"]
    assert starter["tasks"][1]["skills"] == ["Small Edged"]
    assert starter["tasks"][1]["stop_word"] == "stop"
    assert validate(starter) == []


def test_validate_names_what_would_break_the_loop():
    broken = plan(
        order="random",
        target=40,
        tasks=[
            {"name": "both", "script": "hunt", "commands": ["x"]},
            {"name": "neither"},
            {"name": "neither", "script": "hunt"},
        ],
    )
    problems = validate(broken)
    assert any("order" in line for line in problems)
    assert any("target 40" in line for line in problems)
    assert any("both" in line and "not both" in line for line in problems)
    assert any("neither" in line and "no script" in line for line in problems)
    assert any("used twice" in line for line in problems)
    assert validate(plan()) == []


# -- the decisions ----------------------------------------------------------


def test_a_task_is_satisfied_when_every_skill_reaches_the_target():
    current = plan()
    rats = current["tasks"][1]
    assert not satisfied(current, rats, exp(Small_Edged=30, Evasion=12))
    assert satisfied(current, rats, exp(Small_Edged=30, Evasion=30))
    # A skill the exp window doesn't show counts as 0.
    assert not satisfied(current, rats, exp(Small_Edged=34))


def test_skill_names_match_ignoring_case():
    current = plan(tasks=[{"script": "hunt", "skills": ["small edged"]}])
    assert satisfied(current, current["tasks"][0], exp(Small_Edged=30))


def test_a_task_target_overrides_the_plans():
    current = plan(
        tasks=[{"script": "athletics", "skills": ["Athletics"], "target": 20}]
    )
    assert satisfied(current, current["tasks"][0], exp(Athletics=20))


def test_a_skill_less_task_is_never_satisfied_so_it_runs_its_budget():
    current = plan(tasks=[{"commands": ["hum"]}])
    assert not satisfied(current, current["tasks"][0], exp(Athletics=34))


def test_next_task_takes_the_plan_in_order_skipping_done_and_spent():
    current = plan()
    experience = exp(Athletics=30, Small_Edged=5, Performance=0)
    assert next_task(current, experience)["name"] == "rats"
    assert next_task(current, experience, spent={"rats"})["name"] == "music"
    assert next_task(current, experience, spent={"rats", "music"}) is None


def test_lowest_order_takes_the_least_trained_task_first():
    current = plan(order="lowest")
    experience = exp(Athletics=12, Small_Edged=20, Evasion=3, Performance=8)
    assert next_task(current, experience)["name"] == "rats"  # Evasion at 3


def test_rested_once_every_tracked_skill_has_drained():
    current = plan(rest_until=10)
    assert tracked_skills(current) == [
        "Athletics",
        "Small Edged",
        "Evasion",
        "Performance",
    ]
    assert not rested(current, exp(Athletics=11, Small_Edged=2))
    assert rested(current, exp(Athletics=10, Small_Edged=2))
    assert rested(current, {})  # nothing learning at all


def test_safe_rooms_rotate_and_an_empty_list_rests_in_place():
    current = plan(safe_rooms=["home", "bank"])
    assert [safe_room(current, i) for i in range(3)] == ["home", "bank", "home"]
    assert safe_room(plan(), 0) is None


def test_describe_and_status_read_like_the_plan():
    lines = describe(plan(safe_rooms=["home"], rest_commands=["sit"]))
    assert lines[0] == "safe rooms: home"
    assert lines[1] == "rest commands: sit"
    assert any(
        "rats: Small Edged, Evasion — ;hunt (stop word 'stop')" in line
        for line in lines
    )
    assert any("music: Performance — play my flute every 5s" in line for line in lines)
    status = status_lines(plan(), exp(Athletics=7))
    assert status[0] == "  Athletics: 7/34"
    assert status[1] == "  Small Edged: 0/34"


def test_the_module_is_reloadable_by_the_script_engine():
    from client.scripting import RELOADABLE_MODULES

    assert "client.training" in RELOADABLE_MODULES
    assert RELOADABLE_MODULES.index("client.training") > RELOADABLE_MODULES.index(
        "client.profile"
    )
    assert training.MIND_LOCK == 34
