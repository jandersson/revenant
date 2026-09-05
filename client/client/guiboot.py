"""Start the GUI with a net under it: `python -m client.guiboot [args]`.

The launcher exec's the GUI as a fresh process, so the startup guard
in tools/desktop.py never sees it, and under pythonw a crash before
logging comes up dies with nowhere to print — a stale venv missing a
new dependency looked exactly like "the launcher does nothing" (#108).
This module imports the GUI inside a try, and:

- a failure to import or start is written to
  ~/.revenant/logs/startup-<stamp>-<pid>.log and shown in a native
  message box on Windows (stderr elsewhere), with the uv sync hint when
  it is an ImportError;
- faulthandler is armed to ~/.revenant/logs/faults-<stamp>-<pid>.log
  for the life of the process, so an abort inside Qt leaves a Python
  stack behind (the dock-layout aborts of #124/#140 were diagnosed only
  by running the GUI from a terminal); a clean exit removes the empty
  file.

Everything here but the final import is stdlib, so the net holds when
the venv is broken.
"""

import atexit
import faulthandler
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def log_dir() -> Path:
    """REVENANT_LOG_DIR, else ~/.revenant/logs — the game logs' home,
    stated here without importing anything that could be broken."""
    return Path(os.environ.get("REVENANT_LOG_DIR", "~/.revenant/logs")).expanduser()


def _stamp():
    return f"{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"


def arm_faulthandler(directory=None):
    """Point faulthandler at a fresh file; returns its path. The file is
    deleted at a clean exit if nothing was written to it."""
    directory = Path(directory) if directory else log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"faults-{_stamp()}.log"
    stream = open(path, "w", encoding="utf-8")
    faulthandler.enable(file=stream, all_threads=True)

    def tidy():
        try:
            stream.flush()
            if path.stat().st_size == 0:
                stream.close()
                path.unlink()
        except OSError:
            pass

    atexit.register(tidy)
    return path


def startup_hint(error):
    """One line telling the user what to do about a startup failure."""
    if isinstance(error, ImportError):
        return "The venv looks out of date for the current code. Fix: run  uv sync  in the repo, then launch again."
    return "Details are in the startup log named above; the debug log may have more."


def report_startup_failure(error, directory=None, show=True):
    """Write the traceback to startup-<stamp>-<pid>.log and tell the
    user; returns the log path. `show` False skips the message box
    (tests, and terminals where stderr suffices)."""
    directory = Path(directory) if directory else log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"startup-{_stamp()}.log"
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(
            f"Revenant GUI failed to start at {datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
        )
        stream.write(
            "".join(traceback.format_exception(type(error), error, error.__traceback__))
        )
    message = f"{type(error).__name__}: {error}\n\nLog: {path}\n\n{startup_hint(error)}"
    if show:
        _show(message)
    return path


def _show(message):
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, message, "Revenant could not start", 0x10
            )
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def main(argv=None):
    arm_faulthandler()
    try:
        from client.gui.client_gui import main as gui_main
    except Exception as error:  # a broken venv is the whole point
        report_startup_failure(error)
        return 1
    try:
        return gui_main(argv)
    except SystemExit:
        raise
    except Exception as error:
        report_startup_failure(error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
