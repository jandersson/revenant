import logging

from client.client_logger import ClientLogger, log_dir


def test_log_files_land_in_configured_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_LOG_DIR", str(tmp_path / "logs"))
    assert log_dir() == tmp_path / "logs"

    ClientLogger().log.debug("hello from the test")
    logging.getLogger("game").info("a line of game text")

    assert (tmp_path / "logs" / "revenant_client.log").exists()
    game_logs = list((tmp_path / "logs").glob("game-*.log"))
    assert len(game_logs) == 1, "one per-session game log expected"
    assert "a line of game text" in game_logs[0].read_text()
