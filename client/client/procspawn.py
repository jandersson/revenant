"""Start a sibling process the way this one was started, frozen or not.

Every `python -m client.session` / `-m beholder.app` spawn goes through
command_for(), so a packaged build (PyInstaller, #60) keeps working:
there is no Python on the path in an installed copy, only the one
executable, which client/frozen.py turns into whatever role it is asked
for with `--role <module>`. bundle_dir() is where the bundled data
(scripts/, the icons) lives in that build.
"""

import sys
from pathlib import Path


def frozen():
    """True inside a PyInstaller build."""
    return bool(getattr(sys, "frozen", False))


def command_for(module, *args):
    """argv that runs `python -m <module> <args>` — or, in a packaged
    build, this executable playing that role."""
    if frozen():
        return [sys.executable, "--role", module, *args]
    return [sys.executable, "-m", module, *args]


def bundle_dir():
    """The packaged build's data directory, None when running from source."""
    root = getattr(sys, "_MEIPASS", None)
    return Path(root) if root else None
