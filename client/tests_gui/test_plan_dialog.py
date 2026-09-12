"""The Training Plan dialog, offscreen: it shows a plan, edits reach
its values coerced the way ;train reads them, tasks add, remove and
reorder, a plan the validator rejects is not accepted, and the values
round-trip through the plan file."""

from client.game.training import (
    DEFAULTS,
    TASK_DEFAULTS,
    load_plan,
    normalize_task,
    save_plan,
)
from client.gui.plan_dialog import NO_VALUE, PlanDialog


def _plan():
    return dict(DEFAULTS) | {
        "safe_rooms": ["home"],
        "rest_commands": ["sit"],
        "tasks": [
            normalize_task(
                {"name": "climbs", "script": "athletics", "skills": ["Athletics"]}
            ),
            normalize_task(
                {
                    "name": "rats",
                    "script": "hunt",
                    "skills": ["Small Edged", "Evasion"],
                    "stop_word": "stop",
                    "minutes": 45,
                },
                1,
            ),
        ],
    }


def test_the_dialog_shows_the_plan_and_gives_it_back_unchanged(qapp):
    dialog = PlanDialog("Lanival", _plan())
    assert dialog.task_list.count() == 2
    assert dialog.plan_widgets["safe_rooms"][1].text() == "home"
    assert dialog.plan_widgets["target"][1].value() == 30
    assert dialog.plan_widgets["order"][1].currentText() == "listed"
    assert dialog.values() == _plan()


def test_edits_to_the_plan_and_a_task_reach_the_values(qapp):
    dialog = PlanDialog("Lanival", _plan())
    dialog.plan_widgets["target"][1].setValue(25)
    dialog.plan_widgets["safe_rooms"][1].setText("home, 1900")
    dialog.plan_widgets["order"][1].setCurrentText("lowest")
    dialog.task_list.setCurrentRow(1)
    assert dialog.task_widgets["minutes"][1].value() == 45
    dialog.task_widgets["minutes"][1].setValue(NO_VALUE)  # blank: the plan's
    dialog.task_widgets["skills"][1].setText("Small Edged, Parry Ability")
    values = dialog.values()
    assert values["target"] == 25
    assert values["safe_rooms"] == ["home", "1900"]
    assert values["order"] == "lowest"
    assert values["tasks"][1]["minutes"] is None
    assert values["tasks"][1]["skills"] == ["Small Edged", "Parry Ability"]
    assert values["tasks"][0]["script"] == "athletics"  # untouched


def test_tasks_add_rename_reorder_and_remove(qapp):
    dialog = PlanDialog("Lanival", _plan())
    dialog.add_task()
    assert dialog.task_list.currentRow() == 2
    dialog.task_widgets["name"][1].setText("music")
    dialog.task_widgets["name"][1].textEdited.emit("music")
    dialog.task_widgets["commands"][1].setText("play my flute")
    dialog.task_widgets["pace"][1].setValue(8)
    assert dialog.task_list.item(2).text() == "music"
    dialog.move_task(-1)
    names = [task["name"] for task in dialog.values()["tasks"]]
    assert names == ["climbs", "music", "rats"]
    assert dialog.values()["tasks"][1]["commands"] == ["play my flute"]
    dialog.task_list.setCurrentRow(0)
    dialog.remove_task()
    names = [task["name"] for task in dialog.values()["tasks"]]
    assert names == ["music", "rats"]
    assert dialog.task_list.count() == 2


def test_a_plan_the_validator_rejects_is_not_accepted(qapp):
    dialog = PlanDialog("Lanival", _plan())
    dialog.add_task()  # a task with no script and no commands
    dialog.try_accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert "names no script and no commands" in dialog.problems.text()
    dialog.task_widgets["script"][1].setText("athletics")
    dialog.try_accept()
    assert dialog.result() == dialog.DialogCode.Accepted


def test_an_empty_plan_starts_with_the_task_form_disabled(qapp):
    dialog = PlanDialog("Lanival", dict(DEFAULTS))
    assert not dialog.task_widgets["name"][1].isEnabled()
    dialog.add_task()
    assert dialog.task_widgets["name"][1].isEnabled()
    assert dialog.values()["tasks"][0] == normalize_task({}, 0)
    assert dialog.values()["tasks"][0]["stop_grace"] == TASK_DEFAULTS["stop_grace"]


def test_values_round_trip_through_the_plan_file(qapp, isolated_files):
    dialog = PlanDialog("Lanival", _plan())
    dialog.plan_widgets["cycles"][1].setValue(2)
    save_plan("Lanival", dialog.values())
    assert load_plan("Lanival") == dialog.values()
    assert load_plan("Lanival")["cycles"] == 2
