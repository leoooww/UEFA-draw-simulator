"""Headless UI test: drives app.py against a *running* Julia backend (JULIA_API_URL, default :8080)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _boot() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception, at.exception
    return at


def test_initial_state_prompts_for_a_run():
    at = _boot()
    assert any("Run draw" in i.value for i in at.info)


def test_run_draw_end_to_end():
    at = _boot()
    at.sidebar.slider[0].set_value(2)
    at.sidebar.button[0].click().run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]

    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Draws"] == "2"
    assert metrics["Rule check"] == "Passed"
    # results table: 36 clubs
    assert any(len(df.value) == 36 for df in at.dataframe)


def test_cached_rerun_is_instant_and_identical():
    at = _boot()
    at.sidebar.checkbox[0].uncheck().run()    # fixed seed -> seed input becomes enabled
    at.sidebar.number_input[0].set_value(123)
    at.sidebar.button[0].click().run()
    first = {m.label: m.value for m in at.metric}
    at.sidebar.button[0].click().run()
    assert {m.label: m.value for m in at.metric} == first   # same seed -> same cached payload
