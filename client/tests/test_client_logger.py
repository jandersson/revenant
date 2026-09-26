"""How ClientLogger configures logging — these tests are the manual.

dictConfig is destructive (replaces root handlers, disables existing
loggers by default), so it runs once per process with
disable_existing_loggers off: a host's handlers and loggers survive
every ClientLogger instantiation after the first.
"""

import logging

from client import client_logger


def test_dictconfig_runs_once_and_preserves_existing_loggers(monkeypatch):
    applied = []
    monkeypatch.setattr(
        client_logger.logging.config,
        "dictConfig",
        lambda config: applied.append(config),
    )
    monkeypatch.setattr(client_logger, "_CONFIGURED", False)
    bystander = logging.getLogger("test.bystander.logger")
    bystander.disabled = False

    class Thing(client_logger.ClientLogger):
        pass

    Thing().log.debug("first instance configures")
    Thing().log.debug("second instance must not reconfigure")

    assert len(applied) == 1
    assert applied[0]["disable_existing_loggers"] is False
    assert not bystander.disabled


def test_the_log_files_carry_the_characters_name():
    # The operator, 2026-09-26: two characters' logs told apart only by
    # opening them. The name follows the prefix; without one, the plain
    # stamped names; only letters, digits and hyphens are kept.
    assert client_logger.log_filenames("Westan", "20260926-195600", 53044) == (
        "game-Westan-20260926-195600.log",
        "revenant_client-Westan-20260926-195600-53044.log",
    )
    assert client_logger.log_filenames(None, "20260926-195600", 7) == (
        "game-20260926-195600.log",
        "revenant_client-20260926-195600-7.log",
    )
    assert client_logger.log_filenames("../Sab le", "s", 1)[0] == "game-Sable-s.log"


def test_the_handlers_take_the_name_from_revenant_character(monkeypatch):
    applied = []
    monkeypatch.setattr(
        client_logger.logging.config,
        "dictConfig",
        lambda config: applied.append(config),
    )
    monkeypatch.setattr(client_logger, "_CONFIGURED", False)
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")

    class Thing(client_logger.ClientLogger):
        pass

    Thing().log.debug("configure")
    handlers = applied[0]["handlers"]
    assert "game-Lanival-" in handlers["game_file"]["filename"]
    assert "revenant_client-Lanival-" in handlers["file"]["filename"]


def test_no_console_handler_without_a_console(monkeypatch):
    # #242: a ;reexec child under pythonw inherited a stdout whose flush
    # raised EINVAL on every record, and reexec-<stamp>.err filled with
    # 900 "Logging error" tracebacks in a minute. Without a tty on
    # stdout the console handler is left out; with one it stays.
    import types

    def configured_with(stdout):
        applied = []
        monkeypatch.setattr(
            client_logger.logging.config,
            "dictConfig",
            lambda config: applied.append(config),
        )
        monkeypatch.setattr(client_logger, "_CONFIGURED", False)
        monkeypatch.setattr(client_logger.sys, "stdout", stdout)

        class Thing(client_logger.ClientLogger):
            pass

        Thing().log.debug("configure")
        return applied[0]

    headless = configured_with(None)
    assert headless["root"]["handlers"] == ["file"]
    assert "console" not in headless["handlers"]
    piped = configured_with(types.SimpleNamespace(closed=False, isatty=lambda: False))
    assert piped["root"]["handlers"] == ["file"]

    class Broken:
        closed = False

        def isatty(self):
            raise OSError(22, "Invalid argument")

    assert configured_with(Broken())["root"]["handlers"] == ["file"]
    tty = configured_with(types.SimpleNamespace(closed=False, isatty=lambda: True))
    assert tty["root"]["handlers"] == ["console", "file"]
    assert tty["handlers"]["console"]["stream"] == "ext://sys.stdout"


def test_debug_log_is_per_process_and_prunes_old_ones(monkeypatch, tmp_path):
    # Rotating one shared revenant_client.log contends across processes
    # on Windows (#74): the filename carries the session stamp and pid,
    # and stale disposable logs are pruned at init — the game-* archive
    # is never touched.
    import os

    applied = []
    monkeypatch.setattr(
        client_logger.logging.config,
        "dictConfig",
        lambda config: applied.append(config),
    )
    monkeypatch.setattr(client_logger, "_CONFIGURED", False)
    monkeypatch.setenv("REVENANT_LOG_DIR", str(tmp_path))
    old_debug = tmp_path / "revenant_client-20200101-000000-42.log"
    old_debug.write_text("stale")
    os.utime(old_debug, (0, 0))
    old_game = tmp_path / "game-20200101-000000.log"
    old_game.write_text("archive")
    os.utime(old_game, (0, 0))

    class Thing(client_logger.ClientLogger):
        pass

    Thing().log.debug("configure")

    filename = applied[0]["handlers"]["file"]["filename"]
    assert f"-{os.getpid()}.log" in filename
    assert "revenant_client-" in filename
    assert not old_debug.exists()  # disposable and stale: pruned
    assert old_game.exists()  # the archive outlives every prune
