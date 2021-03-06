import sys
from threading import Thread
from time import sleep

from PyQt5.QtWidgets import QAction, qApp, QApplication, QDockWidget, QLineEdit, QMainWindow, QMenu, QTextEdit
from PyQt5.QtGui import QIcon, QTextCursor
from PyQt5.QtCore import Qt

from client.core import Client


class ClientGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.input_buffer = []
        self.status_bar = self.statusBar()
        self.input_dock = QDockWidget()
        self.client = Client(mode='gui')
        self.__init_ui()
        self.client.start()
        self.gui_reactor()

    def __init_ui(self):
        self.setWindowTitle('Revenant')
        self.status_bar.showMessage('Not Connected')

        self.__add_output_window()
        self.__add_input_field()

        exit_action = QAction(QIcon('exit.png'), '&Exit', self)
        exit_action.setShortcut('Ctrl-Q')
        exit_action.setStatusTip('Exit')
        exit_action.triggered.connect(qApp.quit)

        view_status_bar = QAction('Status Bar', self, checkable=True)
        view_status_bar.setStatusTip('Show the status bar')
        view_status_bar.setChecked(True)
        view_status_bar.triggered.connect(self.toggle_menu)

        menubar = self.menuBar()
        file_menu = menubar.addMenu('&File')
        file_menu.addAction(exit_action)
        view_menu = menubar.addMenu('View')
        view_menu.addAction(view_status_bar)

        self.show()

    def __add_output_window(self):
        self.main_window = QTextEdit(readOnly=True)
        self.setCentralWidget(self.main_window)

    def __add_input_field(self):
        self.input = QLineEdit()
        #self.input = QInputDialog()
        self.input_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.input_dock.setWidget(self.input)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.input_dock)
        self.input.returnPressed.connect(self.write_to_input_buffer)

    def write_to_input_buffer(self):
        self.input_buffer.append(self.input.text())

    def toggle_menu(self, state):
        if state:
            self.status_bar.show()
        else:
            self.status_bar.hide()

    def write_to_main_window(self, text):
        if not text.endswith('\n'):
            text = text + '\n'
        self.main_window.insertPlainText(text)
        self.main_window.moveCursor(QTextCursor.End)

    def write(self, write_data: str):
        write_data = write_data + '\n'
        self.client.connection.write(write_data.encode('ASCII'))
        self.write_to_main_window(f'>{write_data}')
        self.input.clear()

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        exit_action = context_menu.addAction('Quit')
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        if action == exit_action:
            qApp.quit()

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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    client_app = ClientGUI()
    sys.exit(app.exec_())
