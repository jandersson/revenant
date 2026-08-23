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
