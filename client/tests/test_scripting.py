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


def test_get_with_zero_timeout_polls_queued_frames_without_blocking(tmp_path):
    # go2 drains stale compass frames this way before each move.
    manager, recorder = make_manager(tmp_path)
    script = Script("t", [], manager)
    script.feed("n e", "compass")
    script.feed("s w", "compass")
    assert script.get(timeout=0, streams=("compass",)) == "n e"
    assert script.get(timeout=0, streams=("compass",)) == "s w"
    assert script.get(timeout=0, streams=("compass",)) is None  # queue drained


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


def test_k_and_kill_are_stop_aliases(tmp_path):
    (tmp_path / "waiter.py").write_text(
        "def main(s):\n    while True:\n        s.sleep(5)\n"
    )
    manager, recorder = make_manager(tmp_path)
    manager.start("waiter", [])
    assert wait_for(lambda: manager.running.get("waiter"))
    manager.handle_command(";k waiter")  # lich muscle memory
    assert wait_for(lambda: not manager.running)
    assert any("waiter stopped" in e for e in recorder.emitted)
    # ;kill with nothing running answers like ;stop does.
    manager.handle_command(";kill")
    assert any("nothing to stop" in e for e in recorder.emitted)


LOOPER = "def main(s):\n    while True:\n        s.sleep(0.05)\n"


def test_stop_by_unique_prefix(tmp_path):
    # ;k mech stops mechlore when nothing else matches the prefix.
    (tmp_path / "mechlore.py").write_text(LOOPER)
    manager, recorder = make_manager(tmp_path)
    manager.start("mechlore", [])
    assert wait_for(lambda: "mechlore" in manager.running)
    manager.stop("mech")
    assert wait_for(lambda: any("mechlore stopped" in e for e in recorder.emitted))


def test_stop_prefix_matching_several_scripts_refuses(tmp_path):
    (tmp_path / "mecha.py").write_text(LOOPER)
    (tmp_path / "mechb.py").write_text(LOOPER)
    manager, recorder = make_manager(tmp_path)
    manager.start("mecha", [])
    manager.start("mechb", [])
    assert wait_for(lambda: len(manager.running) == 2)
    manager.stop("mech")
    assert any("matches several" in e and "mecha, mechb" in e for e in recorder.emitted)
    assert all("stopped" not in e for e in recorder.emitted)
    manager.stop("all")
    assert wait_for(lambda: not manager.running)


def test_stop_exact_name_beats_the_prefix(tmp_path):
    # A script named exactly "mech" stops alone while "mechlore" runs on.
    (tmp_path / "mech.py").write_text(LOOPER)
    (tmp_path / "mechlore.py").write_text(LOOPER)
    manager, recorder = make_manager(tmp_path)
    manager.start("mech", [])
    manager.start("mechlore", [])
    assert wait_for(lambda: len(manager.running) == 2)
    manager.stop("mech")
    assert wait_for(lambda: any("mech stopped" in e for e in recorder.emitted))
    assert "mechlore" in manager.running
    assert all("mechlore stopped" not in e for e in recorder.emitted)
    manager.stop("all")
    assert wait_for(lambda: not manager.running)


def test_stop_unmatched_prefix_reports_nothing_to_stop(tmp_path):
    manager, recorder = make_manager(tmp_path)
    manager.stop("mech")
    assert "nothing to stop (mech)" in recorder.emitted


def test_dead_reflects_the_death_indicator(tmp_path):
    manager, recorder = make_manager(tmp_path)
    script = Script("t", [], manager)
    assert script.dead is False  # no parser state at all yet
    manager.state = types.SimpleNamespace(indicator={"IconDEAD": "y"})
    assert script.dead is True
    manager.state.indicator["IconDEAD"] = "n"
    assert script.dead is False


# --- helper modules reload on script start (#138) ---


def _write_helper(path, value, stamp):
    path.write_text(f"VALUE = {value}\n")
    # Editors and git may leave mtimes anywhere; the stamp is what the
    # engine compares, so set it explicitly and distinctly.
    import os

    os.utime(path, (stamp, stamp))


def _reload_fixture(tmp_path, monkeypatch):
    """A throwaway helper module on sys.path, a manager that treats it
    as reloadable, and a script that echoes the helper's VALUE."""
    import sys

    monkeypatch.syspath_prepend(str(tmp_path))
    helper = tmp_path / "hot_helper.py"
    _write_helper(helper, 1, 1_000_000)
    sys.modules.pop("hot_helper", None)
    (tmp_path / "probe_it.py").write_text(
        "import hot_helper\n\ndef main(s):\n    s.echo(str(hot_helper.VALUE))\n"
    )
    recorder = Recorder()
    manager = ScriptManager(
        send=recorder.sent.append,
        emit=recorder.emitted.append,
        scripts_dir=tmp_path,
        reloadable=("hot_helper",),
    )
    return manager, recorder, helper


def _run_and_wait(manager, recorder, name="probe_it"):
    before = len(recorder.emitted)
    manager.start(name, [])
    assert wait_for(
        lambda: any(f"{name} exited" in e for e in recorder.emitted[before:])
    )
    return recorder.emitted[before:]


def test_a_helper_edited_since_import_is_reloaded_at_the_next_start(
    tmp_path, monkeypatch
):
    manager, recorder, helper = _reload_fixture(tmp_path, monkeypatch)
    first = _run_and_wait(manager, recorder)
    assert "[probe_it] 1" in first
    assert not any("reloaded" in e for e in first)

    _write_helper(helper, 2, 2_000_000)
    second = _run_and_wait(manager, recorder)
    assert "[probe_it] 2" in second  # the script saw the fresh module
    assert any(e == "reloaded hot_helper (edited since import)" for e in second)


def test_an_unchanged_helper_is_left_alone(tmp_path, monkeypatch):
    manager, recorder, helper = _reload_fixture(tmp_path, monkeypatch)
    _run_and_wait(manager, recorder)
    second = _run_and_wait(manager, recorder)
    assert not any("reloaded" in e for e in second)
    assert "[probe_it] 1" in second


def test_a_helper_not_yet_imported_is_not_touched(tmp_path, monkeypatch):
    import sys

    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("never_imported_helper", None)
    (tmp_path / "noop.py").write_text("def main(s):\n    s.echo('ok')\n")
    recorder = Recorder()
    manager = ScriptManager(
        send=recorder.sent.append,
        emit=recorder.emitted.append,
        scripts_dir=tmp_path,
        reloadable=("never_imported_helper",),
    )
    out = _run_and_wait(manager, recorder, "noop")
    assert "[noop] ok" in out
    assert "never_imported_helper" not in sys.modules


def test_a_broken_edit_keeps_the_old_helper_and_says_so(tmp_path, monkeypatch):
    manager, recorder, helper = _reload_fixture(tmp_path, monkeypatch)
    _run_and_wait(manager, recorder)
    helper.write_text("VALUE = (\n")  # a half-typed edit
    import os

    os.utime(helper, (3_000_000, 3_000_000))
    second = _run_and_wait(manager, recorder)
    assert any("hot_helper failed to reload, keeping the old code" in e for e in second)
    assert "[probe_it] 1" in second  # last good code still runs


def test_the_reloadable_list_never_names_the_sessions_plumbing():
    from client.scripting import RELOADABLE_MODULES

    for forbidden in (
        "client.session",
        "client.core",
        "client.xml_data",
        "client.scripting",
    ):
        assert forbidden not in RELOADABLE_MODULES
    # Dependency order: walker binds names from mapdb, which must go first.
    assert RELOADABLE_MODULES.index("client.mapdb") < RELOADABLE_MODULES.index(
        "client.walker"
    )
