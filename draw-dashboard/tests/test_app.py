"""Headless UI tests for app.py with native animated table and click-to-draw workflow."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _boot() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    return at


def test_initial_state_prompts_to_click_draw():
    at = _boot()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    # Initially, no metrics are rendered; prompt is shown
    assert any("click Draw to simulate" in i.value for i in at.info)
    assert len(at.metric) == 0


def test_click_draw_renders_native_animated_table():
    at = _boot()
    draw_btn = next(b for b in at.sidebar.button if b.label == "Draw")
    draw_btn.click().run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]

    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Draws"] == "1"
    assert metrics["Rule check"] == "Passed"
    assert "True compute time" in metrics
    assert metrics["True compute time"].endswith("s")

    # Verify native animated table is rendered with full cell green sweep
    assert any("cellFadeGreenSweep" in m.value for m in at.markdown)
    assert any("draw-table" in m.value for m in at.markdown)

    # Verify download buttons are rendered
    assert len(at.download_button) >= 2


def test_10_draw_sample_aggregation():
    at = _boot()
    # Select 10-draw sample radio in sidebar
    sample_radio = next(r for r in at.sidebar.radio if "Sample type" in r.label)
    sample_radio.set_value("10-draw sample (Strength Analysis)").run()

    # Click Draw button
    draw_btn = next(b for b in at.sidebar.button if b.label == "Draw")
    draw_btn.click().run()
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
        assert len(at.sidebar.button) >= 1
