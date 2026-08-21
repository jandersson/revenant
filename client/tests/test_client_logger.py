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
