import time
import types

from client.scripting import Script, ScriptManager


class Recorder:
    def __init__(self):
        self.sent = []
        self.emitted = []


def make_manager(tmp_path):
    recorder = Recorder()
    manager = ScriptManager(
        send=recorder.sent.append, emit=recorder.emitted.append, scripts_dir=tmp_path
    )
    return manager, recorder


def wait_for(condition, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_run_script_puts_and_echoes(tmp_path):
    (tmp_path / "greet.py").write_text(
        "def main(s):\n    s.echo('hi ' + ' '.join(s.args))\n    s.put('look')\n"
    )
    manager, recorder = make_manager(tmp_path)
    manager.start("greet", ["there"])
    assert wait_for(lambda: any("exited" in e for e in recorder.emitted))
    assert "[greet] hi there" in recorder.emitted
    assert "[greet]> look" in recorder.emitted
    assert recorder.sent == ["look"]
    assert not manager.running


def test_waitfor_matches_fed_lines(tmp_path):
    (tmp_path / "watch.py").write_text(
        "def main(s):\n"
        "    line = s.waitfor(r'troll', timeout=5)\n"
        "    s.echo('saw: ' + str(line))\n"
    )
    manager, recorder = make_manager(tmp_path)
    manager.start("watch", [])
    assert wait_for(lambda: manager.running)
    manager.feed("A troll lumbers in.", "")
    assert wait_for(
        lambda: any("saw: A troll lumbers in." in e for e in recorder.emitted)
    )


def test_stop_interrupts_sleeping_script(tmp_path):
    (tmp_path / "loop.py").write_text(
        "def main(s):\n    while True:\n        s.sleep(10)\n"
    )
    manager, recorder = make_manager(tmp_path)
    manager.start("loop", [])
    assert wait_for(lambda: "loop" in manager.running)
    manager.handle_command(";stop loop")
    assert wait_for(lambda: any("stopped" in e for e in recorder.emitted))
    assert wait_for(lambda: not manager.running)


def test_crash_is_reported_with_location(tmp_path):
    (tmp_path / "boom.py").write_text("def main(s):\n    raise ValueError('kaboom')\n")
    manager, recorder = make_manager(tmp_path)
    manager.start("boom", [])
    assert wait_for(lambda: any("crashed" in e for e in recorder.emitted))
    crash = next(e for e in recorder.emitted if "crashed" in e)
    assert "kaboom" in crash and "boom.py" in crash


def test_double_start_is_refused(tmp_path):
    (tmp_path / "loop.py").write_text(
        "def main(s):\n    while True:\n        s.sleep(10)\n"
    )
    manager, recorder = make_manager(tmp_path)
    manager.start("loop", [])
    assert wait_for(lambda: "loop" in manager.running)
    manager.start("loop", [])
    assert any("already running" in e for e in recorder.emitted)
    manager.stop_all()


def _script_with_state(tmp_path, **state):
    manager, recorder = make_manager(tmp_path)
    defaults = {"server_time": None, "roundtime": 0, "casttime": 0}
    manager.state = types.SimpleNamespace(**{**defaults, **state})
    return Script("t", [], manager), manager.state


def test_waitrt_sleeps_out_roundtime(tmp_path):
    script, state = _script_with_state(tmp_path, server_time=100, roundtime=103)
    slept = []

    def fake_sleep(seconds):
        slept.append(seconds)
        state.server_time = 104  # a fresher prompt arrived while sleeping

    script.sleep = fake_sleep
    script.waitrt()
    assert len(slept) == 1 and 3 <= slept[0] <= 3.5


def test_waitrt_trusts_local_sleep_without_fresh_prompts(tmp_path):
    script, state = _script_with_state(tmp_path, server_time=100, casttime=102)
    slept = []
    script.sleep = lambda seconds: slept.append(seconds)  # clock never advances
    script.waitrt()
    assert len(slept) == 1, "must not spin when no new prompt arrives"


def test_waitrt_is_a_noop_outside_roundtime(tmp_path):
    script, state = _script_with_state(tmp_path, server_time=100, roundtime=90)
    script.sleep = lambda seconds: (_ for _ in ()).throw(AssertionError("slept"))
    script.waitrt()


def test_handle_command_list_and_unknown(tmp_path):
    (tmp_path / "hello.py").write_text("def main(s):\n    pass\n")
    manager, recorder = make_manager(tmp_path)
    manager.handle_command(";list")
    assert any("available" in e and "hello" in e for e in recorder.emitted)
    manager.handle_command(";nosuch")
    assert any("no script named 'nosuch'" in e for e in recorder.emitted)
