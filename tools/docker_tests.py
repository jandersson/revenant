"""Run the CI test battery in Linux containers:  uv run python tools/docker_tests.py

Linux is the OS CI runs and the one with the socket gotcha (closing a
socket does not wake a thread blocked in recv() there — CLAUDE.md), so
Linux-only hangs surface here instead of after a push. Builds
docker/tests.Dockerfile and runs ruff plus the three pytest suites
exactly as .github/workflows/python-package.yml does. Default is
Python 3.12; --all runs the full 3.10-3.12 CI matrix, --python X.Y one
specific version. macOS cannot run in Docker — the workflow's
macos-latest leg covers that OS in CI (#84).
"""

import argparse
import subprocess
import sys
from pathlib import Path

MATRIX = ("3.10", "3.11", "3.12")
DEFAULT = "3.12"
REPO = Path(__file__).resolve().parents[1]


def battery(version):
    """Build and run the test image for one Python; True when green."""
    tag = f"revenant-tests:py{version}"
    build = [
        "docker",
        "build",
        "--file",
        "docker/tests.Dockerfile",
        "--build-arg",
        f"PYTHON_VERSION={version}",
        "--tag",
        tag,
        ".",
    ]
    if subprocess.run(build, cwd=REPO).returncode != 0:
        return False
    return subprocess.run(["docker", "run", "--rm", tag], cwd=REPO).returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Run the CI test battery in Linux containers."
    )
    parser.add_argument(
        "--all", action="store_true", help="run the full CI matrix (3.10-3.12)"
    )
    parser.add_argument(
        "--python",
        metavar="X.Y",
        help=f"run one specific Python (default {DEFAULT})",
    )
    arguments = parser.parse_args()
    versions = MATRIX if arguments.all else (arguments.python or DEFAULT,)
    probe = subprocess.run(["docker", "info"], capture_output=True)
    if probe.returncode != 0:
        sys.exit(
            "docker daemon not reachable — start Docker Desktop "
            "(or the docker service) and retry"
        )
    failed = []
    for version in versions:
        print(f"=== Python {version} ===", flush=True)
        if not battery(version):
            failed.append(version)
    if failed:
        sys.exit(f"FAILED on Python {', '.join(failed)}")
    print(f"all green on Python {', '.join(versions)}")


if __name__ == "__main__":
    main()
