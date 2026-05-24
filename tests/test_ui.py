"""Unit tests for the banner / spinner / signature bars."""

from io import StringIO

from rich.console import Console

from optima import ui


def test_signature_bars_deterministic():
    """Same seed -> same bars (so each query has a stable visual fingerprint)."""
    a = ui.signature_bars("vendor contract hallucinations")
    b = ui.signature_bars("vendor contract hallucinations")
    assert a == b
    assert len(a) == 44
    # every char is one of the block runes we ship
    assert all(c in "▁▂▃▄▅▆▇█" for c in a)


def test_signature_bars_differ_by_seed():
    assert ui.signature_bars("query a") != ui.signature_bars("query b")


def test_signature_bars_width():
    assert len(ui.signature_bars("x", width=10)) == 10
    assert len(ui.signature_bars("x", width=80)) == 80


def test_live_status_disabled_is_a_noop():
    """When disabled (e.g. --json / non-TTY) the context manager must not draw."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=False)
    with ui.live_status(console, enabled=False) as set_phase:
        set_phase("anything")  # must not raise, must not write
    assert buf.getvalue() == ""


def test_render_banner_includes_wordmark_and_bars():
    """Sanity: the banner prints both signature bars and the OPTIMA wordmark."""
    buf = StringIO()
    Console(file=buf, force_terminal=False, width=80).print  # warm up width
    console = Console(file=buf, force_terminal=False, width=80)
    ui.render_banner(console, seed="x")
    out = buf.getvalue()
    assert "OPTIMA" in out.replace(" ", "") or "╔═╗" in out  # wordmark line present
    assert any(c in out for c in "▁▂▃▄▅▆▇█")                  # at least one block char
