import logging.config
import os
import pathlib
import sys
import time
from datetime import datetime

import yaml

# One stamp per process: every logger init in this process appends to the
# same per-session game log instead of fragmenting across files.
_SESSION_STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")

# The debug log is per-process too (stamp plus pid — a session and the
# GUI attaching to it start within the same second): rotating one
# shared revenant_client.log across processes contends on Windows,
# where a rename fails while another process holds the file (#74).
# Unlike the game log (an archive), debug logs are disposable — inits
# prune ones this many days old.
DEBUG_LOG_KEEP_DAYS = 7

# dictConfig is destructive — it replaces root's handlers and (by
# default) disables every logger that already exists. Running it once
# per process, with disable_existing_loggers off, keeps a host's
# handlers (pytest's caplog, an embedding app) and loggers alive.
_CONFIGURED = False


def log_dir() -> pathlib.Path:
    """Where log files live: REVENANT_LOG_DIR, or ~/.revenant/logs.

    A fixed home instead of the process cwd, so the game log accumulates
    in one place no matter where anything was launched from."""
    return pathlib.Path(
        os.environ.get("REVENANT_LOG_DIR", "~/.revenant/logs")
    ).expanduser()


def console_usable():
    """True when sys.stdout is a console worth a StreamHandler: present,
    open and a tty. A pythonw process — the GUI, the session, a ;reexec
    child — has None, or a dead handle whose flush raises EINVAL on
    every record; a redirected stdout is a file the debug log already
    covers (#242)."""
    stream = sys.stdout
    try:
        return stream is not None and not stream.closed and stream.isatty()
    except (AttributeError, ValueError, OSError):
        return False


def prune_debug_logs(directory, keep_days=DEBUG_LOG_KEEP_DAYS):
    """Delete stamped debug logs older than keep_days. Only the
    disposable revenant_client-* files — the game-* archive is never
    touched. Errors are ignored: another process may be pruning too."""
    cutoff = time.time() - keep_days * 86400
    for path in directory.glob("revenant_client-*.log*"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


class ClientLogger:
    def _init_logger(self):
        global _CONFIGURED
        if _CONFIGURED:
            return
        log_conf_path = pathlib.Path(__file__).parents[0] / "logging_config.yaml"
        with open(log_conf_path, "r") as stream:
            config = yaml.load(stream, Loader=yaml.FullLoader)

        directory = log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        for handler in config["handlers"].values():
            if "filename" in handler:
                handler["filename"] = str(directory / handler["filename"])
        config["handlers"]["game_file"]["filename"] = str(
            directory / f"game-{_SESSION_STAMP}.log"
        )
        config["handlers"]["file"]["filename"] = str(
            directory / f"revenant_client-{_SESSION_STAMP}-{os.getpid()}.log"
        )
        prune_debug_logs(directory)
        config["disable_existing_loggers"] = False
        if not console_usable():
            # No console, no console handler: a ;reexec child under
            # pythonw inherited a stdout whose flush failed on every
            # record, and its stderr file held 900 "Logging error"
            # tracebacks within a minute — burying what the file is
            # for, the handoff's own errors (#242, #162).
            config["root"]["handlers"] = [
                name for name in config["root"]["handlers"] if name != "console"
            ]
            config["handlers"].pop("console", None)

        logging.config.dictConfig(config)
        _CONFIGURED = True

    @property
    def log(self):
        """Shamelessly copied from Airflow"""
        try:
            return self._log
        except AttributeError:
            self._init_logger()
            self._log = logging.root.getChild(
                self.__class__.__module__ + "." + self.__class__.__name__
            )
            return self._log
