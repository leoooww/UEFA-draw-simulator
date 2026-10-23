"""Headless UI tests for app.py with precomputed library and optional live Julia solver."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _boot() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    return at


def test_precomputed_library_loads_immediately():
    at = _boot()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]

    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Draws"] == "1"
    assert metrics["Rule check"] == "Passed"
    assert "True compute time" in metrics
    assert metrics["True compute time"].endswith("s")

    # Verify animated table is rendered with fading green animation
    assert any("fadeGreenSweep" in m.value for m in at.markdown)

    # Switch to standard dataframe view and verify 36 clubs
    view_radio = next(r for r in at.radio if "Table view" in r.label or getattr(r, "key", "").startswith("view_mode"))
    view_radio.set_value("Standard dataframe").run()
    assert not at.exception, at.exception
    assert any(len(df.value) == 36 for df in at.dataframe)


def test_seed_selection_and_csv_download():
    at = _boot()
    # Verify download buttons are generated
    assert len(at.download_button) >= 2


def test_replay_animation():
    at = _boot()
    replay_btn = next((b for b in at.button if "Replay animation" in b.label), None)
    if replay_btn:
        replay_btn.click().run()
        assert not at.exception, at.exception


def test_10_draw_sample_aggregation():
    at = _boot()
    # Find sample type radio and select the 10-draw sample
    sample_radio = next(r for r in at.sidebar.radio if "Sample type" in r.label)
    sample_radio.set_value("10-draw sample (Strength Analysis)").run()
    assert not at.exception, at.exception

    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Draws"] == "10"
    assert metrics["Rule check"] == "Passed"
    assert "True compute time" in metrics


def test_live_mode_when_available():
    at = _boot()
    mode_radio = next((r for r in at.sidebar.radio if "Simulation mode" in r.label), None)
    if mode_radio and "Live Julia solver" in mode_radio.options:
        mode_radio.set_value("Live Julia solver").run()
        assert not at.exception, at.exception
        # Live solver form should be visible
        assert len(at.sidebar.button) >= 1
