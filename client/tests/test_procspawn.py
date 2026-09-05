"""How a packaged build keeps spawning itself — these tests are the
manual (#60). From source a sibling process is `python -m module`; in
a PyInstaller build it is this executable with `--role module`, which
client/frozen.py dispatches; the bundled scripts seed
~/.revenant/scripts once and are never overwritten.
"""

import sys

from client import frozen, procspawn
from client.scripting import seed_scripts


def test_from_source_a_sibling_is_python_dash_m(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert procspawn.command_for("client.session", "--port", "4242") == [
        sys.executable,
        "-m",
        "client.session",
        "--port",
        "4242",
    ]
    assert procspawn.bundle_dir() is None


def test_in_a_bundle_a_sibling_is_this_executable_with_a_role(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert procspawn.command_for("beholder.app") == [
        sys.executable,
        "--role",
        "beholder.app",
    ]
    assert procspawn.bundle_dir() == tmp_path


def test_the_role_leads_the_argv_and_the_launcher_is_the_default():
    assert frozen.split_role(["--role", "client.session", "--port", "1"]) == (
        "client.session",
        ["--port", "1"],
    )
    assert frozen.split_role(["--pick"]) == ("client.launch", ["--pick"])
    assert frozen.split_role([]) == ("client.launch", [])


def test_every_role_names_a_module_with_a_main():
    import importlib

    for role, module_name in frozen.ROLES.items():
        assert role == module_name
        assert module_name in (
            "client.launch",
            "client.session",
            "beholder.app",
            "client.gui.chat_window",
            "client.tui",
            "client.sendcmd",
        )
    # The Qt-free ones can be imported here; the GUI ones cannot (headless CI).
    for module_name in ("client.session", "client.sendcmd", "client.tui"):
        assert callable(importlib.import_module(module_name).main)


def test_an_unknown_role_is_refused_with_a_hint(capsys):
    assert frozen.run("client.nonsense", []) == 2
    assert "unknown role" in capsys.readouterr().err


def test_the_bundled_scripts_seed_the_user_directory_once(tmp_path):
    bundled = tmp_path / "bundle" / "scripts"
    bundled.mkdir(parents=True)
    (bundled / "hello.py").write_text("def main(s):\n    s.echo('hi')\n")
    target = tmp_path / "home" / "scripts"
    assert seed_scripts(target, bundled) == target
    assert (target / "hello.py").read_text().startswith("def main")
    # An edited copy is the user's now: a second seed leaves it alone.
    (target / "hello.py").write_text("edited")
    (bundled / "new.py").write_text("def main(s):\n    pass\n")
    seed_scripts(target, bundled)
    assert (target / "hello.py").read_text() == "edited"
    assert (target / "new.py").exists()  # a script the bundle gained is added
