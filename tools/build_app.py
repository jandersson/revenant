"""Build Revenant.app — a minimal macOS bundle wrapping `revenant`.

Renders the moons SVG into an .icns, writes the bundle skeleton, and
installs it to ~/Applications (override with --dest). The bundle's
executable is a login-shell stub, so REVENANT_* exports from the shell
profile apply when launched from Finder/Spotlight/Dock.

Run:  uv run python tools/build_app.py
"""

import argparse
import os
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SVG = REPO / "client" / "client" / "gui" / "revenant.svg"

STUB = """#!/bin/zsh -l
REPO="{repo}"
cd "$REPO" || exit 1
PY="$REPO/.venv/branded/Revenant"
[[ -x "$PY" ]] || PY="$REPO/.venv/bin/python3"
exec "$PY" -m client.launch
"""

INFO = {
    "CFBundleName": "Revenant",
    "CFBundleDisplayName": "Revenant",
    "CFBundleIdentifier": "io.andersson.revenant",
    "CFBundleVersion": "0.0.1",
    "CFBundleShortVersionString": "0.0.1",
    "CFBundleExecutable": "Revenant",
    "CFBundleIconFile": "Revenant.icns",
    "CFBundlePackageType": "APPL",
    "NSHighResolutionCapable": True,
}


def render_icns(destination: Path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtGui import QGuiApplication, QIcon

    app = QGuiApplication([])  # noqa: F841 -- required for pixmap rendering
    icon = QIcon(str(SVG))
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "Revenant.iconset"
        iconset.mkdir()
        for size in (16, 32, 64, 128, 256, 512):
            icon.pixmap(size, size).save(str(iconset / f"icon_{size}x{size}.png"))
            icon.pixmap(size * 2, size * 2).save(
                str(iconset / f"icon_{size}x{size}@2x.png")
            )
        subprocess.run(
            ["iconutil", "-c", "icns", "-o", str(destination), str(iconset)],
            check=True,
        )


def build(dest_dir: Path) -> Path:
    bundle = dest_dir / "Revenant.app"
    macos = bundle / "Contents" / "MacOS"
    resources = bundle / "Contents" / "Resources"
    macos.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)

    with open(bundle / "Contents" / "Info.plist", "wb") as stream:
        plistlib.dump(INFO, stream)

    stub = macos / "Revenant"
    stub.write_text(STUB.format(repo=REPO))
    stub.chmod(0o755)

    render_icns(resources / "Revenant.icns")
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("~/Applications").expanduser(),
        help="where to install the bundle (default: ~/Applications)",
    )
    args = parser.parse_args()
    if sys.platform != "darwin":
        sys.exit("build_app.py builds a macOS bundle; run it on a Mac")
    args.dest.mkdir(parents=True, exist_ok=True)
    bundle = build(args.dest)
    print(f"built {bundle}")


if __name__ == "__main__":
    main()
