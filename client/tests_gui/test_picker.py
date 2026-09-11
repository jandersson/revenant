"""The character picker keeps running sessions in view: under their own
header, in amber and bold, selected by default — never lost in the
alphabetical roster (#158)."""

from PyQt6.QtCore import Qt

from client.gui.login_dialog import ONLINE_COLOR, CharacterPicker

ROSTER = ["Lanival — online, no window", "Sable", "Lanival", "Uthmor"]


def rows(picker):
    return [picker.list.item(i).text() for i in range(picker.list.count())]


def selectable(picker, index):
    return bool(picker.list.item(index).flags() & Qt.ItemFlag.ItemIsSelectable)


def test_online_rows_sit_under_their_own_header_above_the_roster(qapp):
    picker = CharacterPicker(ROSTER, "Sable", "", online=[ROSTER[0]])
    assert rows(picker) == [
        "Online — attach",
        "Lanival — online, no window",
        "Log in as",
        "Sable",
        "Lanival",
        "Uthmor",
    ]
    assert not selectable(picker, 0) and not selectable(picker, 2)
    assert selectable(picker, 1)


def test_online_rows_are_amber_and_bold(qapp):
    picker = CharacterPicker(ROSTER, "", "", online=[ROSTER[0]])
    online = picker.list.item(1)
    assert online.foreground().color().name() == ONLINE_COLOR
    assert online.font().bold()
    assert not picker.list.item(3).font().bold()


def test_the_default_row_is_selected_and_a_header_never_is(qapp):
    picker = CharacterPicker(ROSTER, ROSTER[0], "", online=[ROSTER[0]])
    assert picker.list.currentItem().text() == ROSTER[0]
    picker = CharacterPicker(ROSTER, "nobody", "", online=[ROSTER[0]])
    assert picker.list.currentItem().text() == ROSTER[0]  # first selectable row


def test_without_running_sessions_the_roster_is_plain(qapp):
    picker = CharacterPicker(["Sable", "Lanival"], "Lanival", "")
    assert rows(picker) == ["Sable", "Lanival"]
    assert picker.list.currentItem().text() == "Lanival"
    assert not picker.list.item(1).font().bold()
