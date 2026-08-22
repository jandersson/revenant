"""Shell-style input history for the GUI's command line (Qt-free).

Up walks back through what was typed, Down walks forward again, and
the unsent draft you were composing survives the browse — exactly a
shell's readline feel (#76). The GUI's input field delegates its
arrow keys here; this module holds all the behavior so it can be
tested without Qt.
"""


class CommandHistory:
    def __init__(self, limit=200):
        self.limit = limit
        self.entries = []
        self._cursor = None  # None: not browsing
        self._draft = ""

    def record(self, text):
        """A command was sent: remember it (once, if it repeats the
        previous entry) and leave browse mode."""
        self._cursor = None
        text = text.strip()
        if not text:
            return
        if self.entries and self.entries[-1] == text:
            return
        self.entries.append(text)
        del self.entries[: -self.limit]

    def previous(self, current):
        """The next-older entry (Up). Entering browse mode stashes the
        in-progress draft. None when there is nothing older."""
        if not self.entries:
            return None
        if self._cursor is None:
            self._draft = current
            self._cursor = len(self.entries)
        if self._cursor == 0:
            return None  # already at the oldest
        self._cursor -= 1
        return self.entries[self._cursor]

    def next(self):
        """The next-newer entry (Down); past the newest, the stashed
        draft comes back and browse mode ends. None when not browsing."""
        if self._cursor is None:
            return None
        self._cursor += 1
        if self._cursor >= len(self.entries):
            self._cursor = None
            return self._draft
        return self.entries[self._cursor]
