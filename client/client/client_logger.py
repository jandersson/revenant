import logging.config
import os
import pathlib
from datetime import datetime

import yaml

# One stamp per process: every logger init in this process appends to the
# same per-session game log instead of fragmenting across files.
_SESSION_STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")

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
        config["disable_existing_loggers"] = False

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
