"""How the dashboard shapes queries into the plot and table."""

from beholder import app


def test_mindstate_figure_has_one_sorted_trace_per_skill():
    series = {
        "Sorcery": {
            "times": ["2026-08-16T10:00:00+00:00"],
            "mindstate": [5],
            "rank": [100],
        },
        "Evasion": {
            "times": ["2026-08-16T10:00:00+00:00"],
            "mindstate": [10],
            "rank": [200],
        },
    }
    figure = app.mindstate_figure(series, "Testchar")
    assert [trace.name for trace in figure.data] == ["Evasion", "Sorcery"]
    assert figure.data[1].y == (5,)
    assert "Testchar" in figure.layout.title.text


def test_mindstate_figure_without_history_is_an_empty_plot():
    figure = app.mindstate_figure({}, None)
    assert len(figure.data) == 0


def test_query_returns_default_when_xp_has_never_run(monkeypatch, tmp_path):
    from beholder import data

    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "empty.db"))
    assert app.query(data.characters, default=[]) == []


def test_layout_hints_at_xp_when_there_is_no_history(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "empty.db"))
    layout = app.serve_layout()
    hints = [
        component.children
        for component in layout.children
        if getattr(component, "id", None) == "empty-hint"
    ]
    assert hints and ";xp" in hints[0]
