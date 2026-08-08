"""
Launches a lich instance and a corresponding profanity instance
"""
import argparse
import os
import socket
from subprocess import Popen, run
from pathlib import Path
from time import sleep
from contextlib import closing

# Paths default to the local toolchain but can be overridden via env vars,
# e.g. REVENANT_LICH=/somewhere/else/lich.rbw
DEFAULT_LICH = Path(os.environ.get("REVENANT_LICH", "~/dragonrealms/lich-5/lich.rbw")).expanduser()
DEFAULT_PROFANITY = Path(
    os.environ.get("REVENANT_PROFANITY", "~/dragonrealms/ProfanityFE/profanity.rb")
).expanduser()
DEFAULT_LOG_DIR = Path(os.environ.get("REVENANT_LOG_DIR", "/tmp"))


def launch_lich(lich_path: Path, lich_args):
    # cwd matters: rbenv resolves lich-5's pinned Ruby via .ruby-version in its directory
    Popen(["ruby", str(lich_path), *lich_args], cwd=lich_path.parent)


def launch_profanity(profanity_path: Path, profanity_args):
    run(["ruby", str(profanity_path), *profanity_args], cwd=profanity_path.parent)


def get_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("character", help="Character name (capitalized), must exist in lich's saved logins")
    parser.add_argument("--lich", type=Path, default=DEFAULT_LICH, help="Path to lich.rbw")
    parser.add_argument("--profanity", type=Path, default=DEFAULT_PROFANITY, help="Path to profanity.rb")
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR, help="Profanity log directory")
    parser.add_argument("--lich-wait", type=float, default=10, help="Seconds to wait for lich before attaching")
    args = parser.parse_args()

    for path, what in [(args.lich, "lich executable"), (args.profanity, "profanity executable"), (args.log_dir, "logging directory")]:
        if not path.exists():
            raise FileNotFoundError(f"Cant find {what}: {path}")

    headless_port = get_free_port()

    lich_args = [
        "--login",
        args.character,
        f"--detachable-client={headless_port}",
        "--without-frontend",
        "--dragonrealms",
    ]

    profanity_args = [
        f"--port={headless_port}",
        f"--log-name={args.character}",
        f"--log-dir={args.log_dir}",
    ]

    launch_lich(args.lich, lich_args)
    sleep(args.lich_wait)
    launch_profanity(args.profanity, profanity_args)


if __name__ == "__main__":
    main()
