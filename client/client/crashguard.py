"""Keep the GUI alive when a Qt slot crashes (#94).

PyQt6 hands an exception escaping a slot to sys.excepthook — and then
aborts the whole process, but only when that hook is still Python's
default one. Installing our own hook is what turns "any stale menu
action kills the window" into a logged, visible, survivable event.
Qt-free on purpose: the headless test suite exercises the hook.
"""

import sys
import traceback


def hook(log, emit_text, emit_status):
    """Build a sys.excepthook: log the full traceback, then surface a
    one-line summary through the two emitters (main-window text and
    status bar). Both must be thread-safe — the GUI routes them through
    its queued signals. KeyboardInterrupt keeps its default behavior:
    Ctrl-C in a terminal run should still end the app."""

    def handle(exc_type, value, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, value, tb)
            return
        try:
            log.error(
                "unhandled exception in a Qt slot", exc_info=(exc_type, value, tb)
            )
        except Exception:  # the hook of last resort must never raise
            pass
        summary = "".join(traceback.format_exception_only(exc_type, value)).strip()
        frames = traceback.extract_tb(tb)
        where = f" ({frames[-1].filename}:{frames[-1].lineno})" if frames else ""
        try:
            emit_text(
                f"GUI error: {summary}{where} — the window survives; "
                "details in revenant_client.log"
            )
        except Exception:
            pass
        try:
            emit_status(f"GUI error: {summary}")
        except Exception:
            pass

    return handle


def install(log, emit_text, emit_status):
    """Install the hook process-wide; returns it (mostly for tests)."""
    sys.excepthook = hook(log, emit_text, emit_status)
    return sys.excepthook
