"""The dock widgets on their own: the history line edit, the outlined
vitals bar, the text views' fonts — no window needed."""

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QWidget

from client.gui.compass_dock import CompassRose
from client.gui.input_strip import HistoryLineEdit, OutlinedBar
from client.gui.text_views import (
    GameTextView,
    fixed_pitch_font,
    font_for,
    style_experience_view,
)


def test_up_and_down_browse_the_history_and_keep_the_draft(qapp):
    line = HistoryLineEdit()
    for text in ("look", "north"):
        line.setText(text)
        line.history.record(text)
    line.setText("dra")
    QTest.keyClick(line, Qt.Key.Key_Up)
    assert line.text() == "north"
    QTest.keyClick(line, Qt.Key.Key_Up)
    assert line.text() == "look"
    QTest.keyClick(line, Qt.Key.Key_Down)
    QTest.keyClick(line, Qt.Key.Key_Down)
    assert line.text() == "dra"  # the unsent draft survives the browse (#76)


def test_the_outlined_bar_paints_its_label_itself(qapp):
    bar = OutlinedBar()
    bar.setRange(0, 100)
    bar.setValue(42)
    bar.setFormat("spirit %p%")
    bar.resize(120, 16)
    assert not bar.isTextVisible()  # Qt's own label is off; ours is painted
    pixmap = QPixmap(bar.size())
    bar.render(pixmap)  # the paintEvent runs without a display
    assert not pixmap.isNull()


def test_a_compass_click_sends_the_direction(qapp):
    sent = []
    rose = CompassRose(send=sent.append)
    rose.resize(190, 150)
    rose.set_exits("n up")
    rose.buttons["n"].click()
    rose.buttons["s"].click()  # disabled: nothing sent
    rose.buttons["up"].click()
    assert sent == ["n", "up"]


def test_a_link_click_hands_the_command_to_the_window(qapp):
    commands = []
    view = GameTextView(commands.append, QWidget())
    view.anchorClicked.emit(QUrl(" look sign "))
    assert commands == ["look sign"]
    assert not view.openLinks()


def test_the_experience_view_keeps_fixed_pitch_unless_overridden(qapp):
    default = QFont("Arial", 11)
    plain = font_for(
        {"font_family": "", "font_size": 0, "dock_fonts": {}}, "Main", default
    )
    assert plain.family() == "Arial" and plain.pointSize() == 11
    sized = font_for(
        {"font_family": "", "font_size": 14, "dock_fonts": {}}, "Main", default
    )
    assert sized.pointSize() == 14
    # Experience is the fixed-pitch font at its own size: the story's
    # family and size never reach it — the dashboard is column-aligned
    # and a 15-point story font made it unreadable (#173) ...
    fixed = fixed_pitch_font()
    experience = font_for(
        {"font_family": "Arial", "font_size": 14, "dock_fonts": {}},
        "Experience",
        default,
    )
    assert experience.family() == fixed.family()
    assert experience.pointSize() == fixed.pointSize()
    # ... and only its own row in Settings changes it.
    overridden = font_for(
        {"font_family": "", "font_size": 0, "dock_fonts": {"Experience": {"size": 8}}},
        "Experience",
        default,
    )
    assert overridden.pointSize() == 8
    assert overridden.family() == fixed.family()
    named = font_for(
        {
            "font_family": "",
            "font_size": 0,
            "dock_fonts": {"Experience": {"family": "Arial"}},
        },
        "Experience",
        default,
    )
    assert named.family() == "Arial"
    view = GameTextView(lambda command: None, QWidget())
    style_experience_view(view)
    assert "No skills learning" in view.placeholderText()
