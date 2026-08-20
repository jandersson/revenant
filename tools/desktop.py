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

from client.launch import main  # noqa: E402

main(["--pick"])
