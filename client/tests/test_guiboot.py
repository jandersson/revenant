"""How a GUI that cannot start says so — the manual (#108).

The launcher exec's the GUI as a new process with no guard; guiboot
puts one there. An import failure lands in a startup log with the
traceback and the uv sync hint; faulthandler writes to a faults log
that is removed again when nothing crashed.
"""

import faulthandler

from client import guiboot


def test_a_startup_failure_is_written_to_a_log_with_the_traceback(tmp_path):
    try:
        raise ModuleNotFoundError("No module named 'networkx'")
    except ModuleNotFoundError as error:
        path = guiboot.report_startup_failure(error, directory=tmp_path, show=False)
    assert path.parent == tmp_path and path.name.startswith("startup-")
    text = path.read_text(encoding="utf-8")
    assert "ModuleNotFoundError: No module named 'networkx'" in text
    assert "Traceback" in text


def test_an_import_error_gets_the_uv_sync_hint():
    assert "uv sync" in guiboot.startup_hint(ImportError("x"))
    assert "uv sync" not in guiboot.startup_hint(RuntimeError("x"))


def test_faulthandler_is_armed_to_a_file_in_the_log_dir(tmp_path):
    path = guiboot.arm_faulthandler(tmp_path)
    assert faulthandler.is_enabled()
    assert path.parent == tmp_path and path.name.startswith("faults-")
    assert path.exists()


def test_log_dir_honours_the_override(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_LOG_DIR", str(tmp_path / "logs"))
    assert guiboot.log_dir() == tmp_path / "logs"
