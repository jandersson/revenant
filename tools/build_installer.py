"""Build the distributable: a PyInstaller bundle, then the installer.

    uv run python tools/build_installer.py [--skip-installer]

Runs PyInstaller on packaging/revenant.spec into dist/Revenant (two
executables: Revenant, windowed, and revenant-cli, console). Then, on
Windows, Inno Setup (iscc on PATH, or the default install location)
writes dist/Revenant-<version>-setup.exe; on macOS, hdiutil writes
dist/Revenant-<version>.dmg around dist/Revenant.app. The release
workflow (.github/workflows/release.yml) runs this on version tags
and attaches what comes out (#60). Prints the paths it produced.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "packaging" / "revenant.spec"
ISS = REPO / "packaging" / "revenant.iss"
DIST = REPO / "dist"
VERSION = "0.0.1"

INNO_DEFAULTS = (
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
)


def run(command, **kwargs):
    print("+", " ".join(str(part) for part in command), flush=True)
    subprocess.run(command, check=True, **kwargs)


def bundle():
    run(
        [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm", "--clean"],
        cwd=REPO,
    )
    return DIST / "Revenant"


def find_iscc():
    found = shutil.which("iscc") or shutil.which("ISCC")
    if found:
        return found
    for candidate in INNO_DEFAULTS:
        if os.path.exists(candidate):
            return candidate
    return None


def installer_windows():
    iscc = find_iscc()
    if iscc is None:
        print(
            "Inno Setup (iscc) not found; the bundle in dist/Revenant is the deliverable"
        )
        return None
    run([iscc, str(ISS)], cwd=REPO)
    return DIST / f"Revenant-{VERSION}-setup.exe"


def installer_macos():
    app = DIST / "Revenant.app"
    if not app.is_dir():
        print(
            "no Revenant.app produced; the bundle in dist/Revenant is the deliverable"
        )
        return None
    dmg = DIST / f"Revenant-{VERSION}.dmg"
    if dmg.exists():
        dmg.unlink()
    run(
        [
            "hdiutil",
            "create",
            "-volname",
            "Revenant",
            "-srcfolder",
            str(app),
            "-ov",
            "-format",
            "UDZO",
            str(dmg),
        ]
    )
    return dmg


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-installer", action="store_true", help="bundle only")
    args = parser.parse_args(argv)
    produced = [bundle()]
    if not args.skip_installer:
        made = installer_windows() if sys.platform == "win32" else None
        if sys.platform == "darwin":
            made = installer_macos()
        if made:
            produced.append(made)
    for path in produced:
        print(f"built {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
