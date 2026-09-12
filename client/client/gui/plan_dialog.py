"""The training plan editor: File → Training Plan… in the client.

The plan ;train runs for the character this window plays
(~/.revenant/training/<name>.json, client/game/training.py): the
plan-level settings as a form, the tasks as an ordered list with add,
remove, up and down, and the selected task as a form of its own —
every row built from training.PLAN_FIELDS and TASK_FIELDS, the schema
;train reads, so a new key appears here the moment it gets a default
and a row. OK coerces the text the way the loop would
(training.normalize) and refuses a plan training.validate rejects,
listing what is wrong under the buttons instead of saving it. ;train
reads the file at each start, so a change reaches the next run
without a restart.
"""

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from client.game.training import (
    DEFAULTS,
    ORDERS,
    PLAN_FIELDS,
    TASK_DEFAULTS,
    TASK_FIELDS,
    normalize,
    normalize_task,
    validate,
)

NO_VALUE = -1  # an "optint" spinner at this reads as blank: the plan's value


def _make_widget(kind, value, help_text):
    if kind == "int":
        widget = QSpinBox()
        widget.setRange(0, 100000)
    elif kind == "optint":
        widget = QSpinBox()
        widget.setRange(NO_VALUE, 100000)
        widget.setSpecialValueText("the plan's")
    elif kind == "choice":
        widget = QComboBox()
        widget.addItems(list(ORDERS))
    else:
        widget = QLineEdit()
        if help_text:
            widget.setPlaceholderText(help_text)
    if help_text and kind != "str" and kind != "list":
        widget.setToolTip(help_text)
    _set_widget(kind, widget, value)
    return widget


def _set_widget(kind, widget, value):
    if kind == "int":
        widget.setValue(int(value or 0))
    elif kind == "optint":
        widget.setValue(NO_VALUE if value is None else int(value))
    elif kind == "choice":
        widget.setCurrentText(str(value or ORDERS[0]))
    else:
        widget.setText(
            ", ".join(value) if isinstance(value, list) else str(value or "")
        )


def _read_widget(kind, widget):
    if kind == "int":
        return widget.value()
    if kind == "optint":
        value = widget.value()
        return None if value == NO_VALUE else value
    if kind == "choice":
        return widget.currentText()
    return widget.text()


class PlanDialog(QDialog):
    def __init__(self, character, plan, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Revenant — Training Plan: {character or 'unnamed'}")
        self.tasks = [dict(task) for task in plan.get("tasks") or []]
        self._current = None  # the task the form shows, as an index
        layout = QVBoxLayout(self)
        intro = QLabel(
            "What ;train runs for this character: the tasks in order, the "
            "mindstate they train to, where to rest and until what."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        columns = QHBoxLayout()
        layout.addLayout(columns)

        plan_form = QFormLayout()
        self.plan_widgets = {}
        for key, label, kind, help_text in PLAN_FIELDS:
            widget = _make_widget(kind, plan.get(key, DEFAULTS[key]), help_text)
            plan_form.addRow(f"{label}:", widget)
            self.plan_widgets[key] = (kind, widget)
        columns.addLayout(plan_form, 1)

        tasks_box = QVBoxLayout()
        columns.addLayout(tasks_box, 1)
        tasks_box.addWidget(QLabel("Tasks, in order:"))
        self.task_list = QListWidget()
        for task in self.tasks:
            self.task_list.addItem(task["name"])
        tasks_box.addWidget(self.task_list)
        row = QHBoxLayout()
        for text, slot in (
            ("Add", self.add_task),
            ("Remove", self.remove_task),
            ("Up", lambda: self.move_task(-1)),
            ("Down", lambda: self.move_task(1)),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            row.addWidget(button)
        tasks_box.addLayout(row)
        task_form = QFormLayout()
        self.task_widgets = {}
        for key, label, kind, help_text in TASK_FIELDS:
            widget = _make_widget(kind, TASK_DEFAULTS[key], help_text)
            task_form.addRow(f"{label}:", widget)
            self.task_widgets[key] = (kind, widget)
        tasks_box.addLayout(task_form)
        self.task_widgets["name"][1].textEdited.connect(self._rename)
        self.task_list.currentRowChanged.connect(self._show_task)
        if self.tasks:
            self.task_list.setCurrentRow(0)
        else:
            self._enable_task_form(False)

        self.problems = QLabel()
        self.problems.setWordWrap(True)
        self.problems.setStyleSheet("color: #b00020")
        layout.addWidget(self.problems)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- the task list ------------------------------------------------------

    def _enable_task_form(self, enabled):
        for _, widget in self.task_widgets.values():
            widget.setEnabled(enabled)

    def _read_task(self):
        return {
            key: _read_widget(kind, w) for key, (kind, w) in self.task_widgets.items()
        }

    def _store_current(self):
        if self._current is not None and 0 <= self._current < len(self.tasks):
            self.tasks[self._current] = self._read_task()

    def _show_task(self, row):
        self._store_current()
        self._current = None
        if not 0 <= row < len(self.tasks):
            self._enable_task_form(False)
            return
        self._enable_task_form(True)
        task = self.tasks[row]
        for key, (kind, widget) in self.task_widgets.items():
            _set_widget(kind, widget, task.get(key, TASK_DEFAULTS[key]))
        self._current = row

    def _rename(self, text):
        item = self.task_list.currentItem()
        if item is not None:
            item.setText(text.strip() or f"task{self.task_list.currentRow() + 1}")

    def add_task(self):
        self._store_current()
        task = normalize_task({}, len(self.tasks))
        self.tasks.append(task)
        self.task_list.addItem(task["name"])
        self.task_list.setCurrentRow(len(self.tasks) - 1)

    def remove_task(self):
        row = self.task_list.currentRow()
        if not 0 <= row < len(self.tasks):
            return
        self._current = None  # never store the form into a gone task
        del self.tasks[row]
        self.task_list.takeItem(row)  # the selection change reloads the form

    def move_task(self, delta):
        row = self.task_list.currentRow()
        new = row + delta
        if not 0 <= row < len(self.tasks) or not 0 <= new < len(self.tasks):
            return
        self._store_current()
        self._current = None
        self.tasks[row], self.tasks[new] = self.tasks[new], self.tasks[row]
        item = self.task_list.takeItem(row)
        self.task_list.insertItem(new, item)
        self.task_list.setCurrentRow(new)

    # -- the result --------------------------------------------------------

    def values(self):
        """The plan as ;train would read it: the forms coerced by
        training.normalize over the defaults."""
        self._store_current()
        plan = {
            key: _read_widget(kind, w) for key, (kind, w) in self.plan_widgets.items()
        }
        plan["tasks"] = list(self.tasks)
        return dict(DEFAULTS) | normalize(plan)

    def try_accept(self):
        problems = validate(self.values())
        if problems:
            self.problems.setText("Not saved:\n" + "\n".join(problems))
            return
        self.accept()
