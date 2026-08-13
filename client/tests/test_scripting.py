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


def test_script_emit_targets_a_stream(tmp_path):
    (tmp_path / "mirror.py").write_text(
        "def main(s):\n    s.emit('psst', 'thoughts')\n"
    )
    recorder = Recorder()
    streamed = []
    manager = ScriptManager(
        send=recorder.sent.append,
        emit=recorder.emitted.append,
        emit_stream=lambda text, stream: streamed.append((text, stream)),
        scripts_dir=tmp_path,
    )
    manager.start("mirror", [])
    assert wait_for(lambda: streamed)
    assert streamed == [("psst", "thoughts")]


def test_script_emit_without_stream_sink_falls_back_to_plain(tmp_path):
    (tmp_path / "mirror.py").write_text(
        "def main(s):\n    s.emit('psst', 'thoughts')\n"
    )
    manager, recorder = make_manager(tmp_path)
    manager.start("mirror", [])
    assert wait_for(lambda: "psst" in recorder.emitted)


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


ECHO_COMMANDS = (
    "def main(s):\n"
    "    while True:\n"
    "        line = s.command(timeout=5)\n"
    "        if line is None:\n"
    "            return\n"
    "        s.echo('got: ' + line)\n"
)


def test_typing_the_script_name_with_a_line_delivers_it(tmp_path):
    # ;lnet chat hey  (while lnet runs) hands "chat hey" to the script.
    (tmp_path / "lnet.py").write_text(ECHO_COMMANDS)
    manager, recorder = make_manager(tmp_path)
    manager.start("lnet", [])
    assert wait_for(lambda: manager.running)
    manager.handle_command(";lnet chat hey")
    assert wait_for(lambda: "[lnet] got: chat hey" in recorder.emitted)
    manager.stop_all()


def test_bare_name_on_a_running_script_is_still_refused(tmp_path):
    (tmp_path / "lnet.py").write_text(ECHO_COMMANDS)
    manager, recorder = make_manager(tmp_path)
    manager.start("lnet", [])
    assert wait_for(lambda: manager.running)
    manager.handle_command(";lnet")
    assert any("already running" in e for e in recorder.emitted)
    manager.stop_all()


def test_chat_shorthand_reaches_the_lnet_script(tmp_path):
    # ;chat hey folks  is lich muscle memory for  ;lnet chat hey folks
    (tmp_path / "lnet.py").write_text(ECHO_COMMANDS)
    manager, recorder = make_manager(tmp_path)
    manager.start("lnet", [])
    assert wait_for(lambda: manager.running)
    manager.handle_command(";chat hey folks")
    assert wait_for(lambda: "[lnet] got: chat hey folks" in recorder.emitted)
    manager.stop_all()


def test_chat_shorthand_starts_lnet_from_cold_and_queues_the_line(tmp_path):
    (tmp_path / "lnet.py").write_text(ECHO_COMMANDS)
    manager, recorder = make_manager(tmp_path)
    manager.handle_command(";chat hey folks")
    assert wait_for(lambda: "[lnet] got: chat hey folks" in recorder.emitted)
    manager.stop_all()


def test_help_lists_scripts_with_docstring_summaries(tmp_path):
    (tmp_path / "walk.py").write_text(
        '"""Walk somewhere:  ;walk <place>\n\nThe long story."""\ndef main(s):\n    pass\n'
    )
    (tmp_path / "bare.py").write_text("def main(s):\n    pass\n")
    manager, recorder = make_manager(tmp_path)
    manager.handle_command(";help")
    assert any("walk — Walk somewhere:  ;walk <place>" in e for e in recorder.emitted)
    assert any("bare — (no help)" in e for e in recorder.emitted)


def test_help_prints_full_docstring_without_running_the_script(tmp_path):
    (tmp_path / "walk.py").write_text(
        '"""Walk somewhere.\n\nThe long story."""\nraise SystemExit("must not run")\n'
    )
    manager, recorder = make_manager(tmp_path)
    manager.handle_command(";help walk")
    assert any("The long story." in e for e in recorder.emitted)


def test_help_unknown_script(tmp_path):
    manager, recorder = make_manager(tmp_path)
    manager.handle_command(";help nosuch")
    assert any("no script named 'nosuch'" in e for e in recorder.emitted)
