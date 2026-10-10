"""tools/drive.py — the outside driver: every send logged as it goes, the
stop file honoured before each one, the pace capped."""

import importlib.util
import pathlib

REPO = pathlib.Path(__file__).parents[2]


def _module():
    spec = importlib.util.spec_from_file_location(
        "drive_tool", REPO / "tools" / "drive.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


drive = _module()


def make(tmp_path, monkeypatch, answers=None):
    monkeypatch.setattr(drive, "STOP_FILE", tmp_path / "drive.stop")
    sent = []
    clock = {"now": 1000.0}

    def sender(command):
        sent.append(command)
        return (answers or {}).get(command, "ok\n")

    def sleep(seconds):
        clock["now"] += seconds

    driver = drive.Driver(
        "Lanival",
        sender=sender,
        clock=lambda: clock["now"],
        sleep=sleep,
        log=tmp_path / "drive.log",
    )
    return driver, sent, clock


def test_every_send_and_its_answer_land_in_the_log_as_they_go(
    tmp_path, monkeypatch, capsys
):
    driver, sent, _ = make(
        tmp_path, monkeypatch, {"look": "[A Room]\nObvious paths: north.\n"}
    )
    assert driver.send("look") == "[A Room]\nObvious paths: north.\n"
    text = (tmp_path / "drive.log").read_text(encoding="utf-8")
    assert ">> look" in text and "[A Room]" in text and "Obvious paths" in text
    assert ">> look" in capsys.readouterr().out  # printed too, unbuffered


def test_the_stop_file_halts_before_the_next_send(tmp_path, monkeypatch):
    driver, sent, _ = make(tmp_path, monkeypatch)
    assert driver.run_steps(["look", "# a note", "", "sleep 2", "north"]) is True
    assert sent == ["look", "north"]
    (tmp_path / "drive.stop").touch()
    assert driver.run_steps(["south"]) is False
    assert sent == ["look", "north"]
    assert "STOP file" in (tmp_path / "drive.log").read_text(encoding="utf-8")


def test_the_pace_is_capped_per_minute(tmp_path, monkeypatch):
    monkeypatch.setattr(drive, "SENDS_PER_MINUTE", 3)
    driver, sent, clock = make(tmp_path, monkeypatch)
    for _ in range(3):
        driver.send("look")
    before = clock["now"]
    driver.send("look")  # the fourth inside the minute waits it out
    assert clock["now"] - before >= 60 - 1e-9
    assert len(sent) == 4
    assert "pace:" in (tmp_path / "drive.log").read_text(encoding="utf-8")


def test_stop_and_go_raise_and_lift_the_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(drive, "STOP_FILE", tmp_path / "drive.stop")
    assert drive.main(["--stop"]) == 0 and (tmp_path / "drive.stop").exists()
    assert drive.main(["--go"]) == 0 and not (tmp_path / "drive.stop").exists()
