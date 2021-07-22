import sys
from threading import Thread
from time import sleep

from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLineEdit,
    QMainWindow,
    QMenu,
    QTextEdit,
)
from PyQt6.QtGui import QIcon, QTextCursor, QAction
from PyQt6.QtCore import Qt

from client.core import Engine
from client.client_logger import ClientLogger

# TODO: Lock the scrollbar when its not all the way at the bottom
# TODO: Exit the game when the window is closed. Make it optional, leaving room for headless potential.


class ClientGUI(QMainWindow, ClientLogger):
    def __init__(self):
        super().__init__()
        self.log.debug("Initializing ClientGUI instance")
        self.input_buffer = []
        self.status_bar = self.statusBar()
        self.input_dock = QDockWidget()
        self.client = Engine()
        self.__init_ui()
        self.client.connect()
        self.gui_reactor()

    def __init_ui(self):
        self.log.debug("Initializing UI")
        self.setWindowTitle("Revenant")
        # TODO: Update this with some sort of connection string when connected
        self.status_bar.showMessage("Not Connected")

        self.__add_output_window()
        self.__add_input_field()

        exit_action = QAction(QIcon("exit.png"), "&Exit", self)
        exit_action.setShortcut("Ctrl-Q")
        exit_action.setStatusTip("Exit")
        exit_action.triggered.connect(QApplication.instance().quit)

        view_status_bar = QAction("Status Bar", self, checkable=True)
        view_status_bar.setStatusTip("Show the status bar")
        view_status_bar.setChecked(True)
        view_status_bar.triggered.connect(self.toggle_menu)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(exit_action)
        view_menu = menubar.addMenu("View")
        view_menu.addAction(view_status_bar)

        self.show()

    def __add_output_window(self):
        self.main_window = QTextEdit(readOnly=True)
        self.setCentralWidget(self.main_window)

    def __add_input_field(self):
        self.input = QLineEdit()
        # TODO: Fix the bottom dock. BottomDock thingy is incompatible with Qt6
        self.input_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.input_dock.setWidget(self.input)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.input_dock)
        self.input.returnPressed.connect(self.write_to_input_buffer)

    def write_to_input_buffer(self):
        self.engine.input_buffer.append(self.input.text())

    def toggle_menu(self, state):
        if state:
            self.status_bar.show()
        else:
            self.status_bar.hide()

    def write_to_main_window(self, text: str):
        if not text.endswith("\n"):
            text = text + "\n"
        self.main_window.insertPlainText(text)
        self.main_window.moveCursor(QTextCursor.MoveOperation.End)

    def write(self, write_data: str):
        write_data = write_data + "\n"
        self.client.connection.write(write_data.encode("ASCII"))
        self.write_to_main_window(f">{write_data}")
        self.input.clear()

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        exit_action = context_menu.addAction("Quit")
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        if action == exit_action:
            QApplication.instance().quit()

    def gui_reactor(self):
        def input_loop():
            while True:
                if self.input_buffer:
                    self.write(self.input_buffer.pop(0))
                sleep(0.01)

        def output_loop():
            callback = self.write_to_main_window
            while True:
                self.client.read(output_callback=callback)
                sleep(0.01)

        Thread(target=output_loop).start()
        Thread(target=input_loop).start()


if __name__ == "__main__":
    # TODO: Break out into a launcher module
    app = QApplication(sys.argv)
    client_app = ClientGUI()
    sys.exit(app.exec())
