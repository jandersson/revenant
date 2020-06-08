"""
Launches a lich instance and a corresponding profanity instance
"""
import socket
from subprocess import Popen, run
from pathlib import Path
from time import sleep
from contextlib import closing


def launch_lich(lich_path: Path, lich_args):
    lich_args.insert(0, str(lich_path))
    Popen(lich_args)


def launch_profanity(profanity_path, profanity_args=[]):
    profanity_args.insert(0, str(profanity_path))
    run(profanity_args)


def get_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


if __name__ == "__main__":
    headless_port = get_free_port()
    character = "Hotdog"

    profanity_log_dir = Path("/tmp/")
    if not profanity_log_dir.exists():
        raise FileNotFoundError("Logging directory does not exist")

    lich_executable = Path("/home/jonas/dragonrealms/lich/lich.rbw")
    if not lich_executable.exists():
        raise FileNotFoundError("Cant find lich executable")

    profanity_executable = Path("/home/jonas/dragonrealms/ProfanityFE/profanity.rb")
    if not profanity_executable.exists():
        raise FileNotFoundError("Cant find profanity executable")

    lich_args = [
        "--login",
        character,
        f"--detachable-client={headless_port}",
        "--without-frontend",
        "--dragonrealms",
    ]

    profanity_args = [
        f"--port={headless_port}",
        f"--log-name={character}",
        f"--log-dir={str(profanity_log_dir)}",
    ]

    launch_lich(lich_executable, lich_args)
    sleep(10)
    launch_profanity(profanity_executable, profanity_args)
