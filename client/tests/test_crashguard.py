"""A crashing Qt slot must not take the window down (#94) — the
excepthook logs the traceback, surfaces a one-line summary in the main
window and status bar, and never raises itself.

Qt-free by design: PyQt6 aborts a slot crash only under the default
sys.excepthook, so installing this one is the whole fix; what the hook
then does is exercised here without a display.
"""

import sys

from client import crashguard


class FakeLog:
    def __init__(self):
        self.errors = []

    def error(self, message, exc_info=None):
        self.errors.append((message, exc_info))


def _unpack_crash():
    """The captured reproduction: File → Reconnect's ValueError."""
    try:
        raise ValueError("not enough values to unpack (expected 3, got 2)")
    except ValueError:
        return sys.exc_info()


def test_hook_logs_and_surfaces_the_crash():
    log, texts, statuses = FakeLog(), [], []
    handle = crashguard.hook(log, texts.append, statuses.append)
    handle(*_unpack_crash())
    assert log.errors and log.errors[0][1][0] is ValueError
    assert "ValueError: not enough values to unpack" in texts[0]
    assert "test_crashguard.py" in texts[0]  # the crash site is named
    assert "the window survives" in texts[0]
    assert statuses[0].startswith("GUI error: ValueError")


def test_keyboard_interrupt_keeps_default_behavior(monkeypatch):
    delegated = []
    monkeypatch.setattr(sys, "__excepthook__", lambda *exc: delegated.append(exc))
    texts = []
    handle = crashguard.hook(FakeLog(), texts.append, texts.append)
    handle(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert delegated and not texts


def test_the_hook_of_last_resort_never_raises():
    class BrokenLog:
        def error(self, *args, **kwargs):
            raise RuntimeError("logging broken too")

    def broken_emit(_):
        raise RuntimeError("emitter broken")

    handle = crashguard.hook(BrokenLog(), broken_emit, broken_emit)
    handle(*_unpack_crash())  # must not raise


def test_a_tracebackless_crash_still_surfaces():
    texts = []
    handle = crashguard.hook(FakeLog(), texts.append, texts.append)
    handle(ValueError, ValueError("no traceback"), None)
    assert "ValueError: no traceback" in texts[0]


def test_install_sets_the_process_hook(monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)  # auto-restore
    installed = crashguard.install(FakeLog(), lambda _: None, lambda _: None)
    assert sys.excepthook is installed
