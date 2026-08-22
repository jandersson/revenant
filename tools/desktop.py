"""Windowless entry point for the Windows Start Menu shortcut.

The venv's pythonw.exe is a uv trampoline that re-launches Python via a
console-subsystem hop, so a shortcut targeting it conjures a terminal
behind the GUI. The shortcut (tools/install_shortcut.ps1) instead runs
the base interpreter's real pythonw.exe on this file, which adds the
venv's site-packages itself — also via PYTHONPATH, so the session
process the launcher spawns inherits it — and starts the launcher in
character-picker mode.
"""

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# The workspace installs its members editable: site-packages only wires
# them up through .pth files, which PYTHONPATH entries never process —
# so the package roots go on the path explicitly (client, plus beholder
# for the ;beholder dashboard spawn), next to the venv's site-packages
# (PyQt6, keyring, dash, ...).
PATHS = [
    str(REPO / "client"),
    str(REPO / "beholder"),
    str(REPO / ".venv" / "Lib" / "site-packages"),
]

sys.path[:0] = PATHS
os.environ["PYTHONPATH"] = os.pathsep.join(
    PATHS + [p for p in [os.environ.get("PYTHONPATH")] if p]
)
os.chdir(REPO)


def _report_startup_failure(error):
    """The shortcut runs windowless: without this, a missing dependency
    (a stale venv after new requirements — #67) or any other startup
    crash dies with nowhere to print. A native message box needs no
    working venv at all."""
    import ctypes

    detail = f"{type(error).__name__}: {error}"
    if isinstance(error, ImportError):
        hint = (
            "The venv looks out of date for the current code.\n"
            "Fix: run  uv sync  in the repo, then launch again."
        )
    else:
        hint = "See ~/.revenant/logs/revenant_client.log for details."
    ctypes.windll.user32.MessageBoxW(
        None, f"{detail}\n\n{hint}", "Revenant failed to start", 0x10
    )


try:
    from client.launch import main

    main(["--pick"])
except Exception as error:
    _report_startup_failure(error)
    raise
