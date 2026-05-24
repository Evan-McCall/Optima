"""Banner, query-seeded sparkline fingerprint, and live spinner.

The banner is a small, calm bit of polish — a wordmark plus a one-line
"signature bar" of unicode blocks derived from a SHA-256 of the query, so every
run carries a unique visual fingerprint without any animation cost.

The spinner is a thin wrapper over rich.Console.status that runs the elapsed
counter in a daemon thread and lets the orchestrator update the current phase
through a callback. Disabled cleanly for --json / non-TTY so machine output
stays pristine.
"""

from __future__ import annotations

import hashlib
import threading
import time
from contextlib import contextmanager
from typing import Callable, Iterator

from rich.console import Console

# Eight visible block heights — index 0 is a thin baseline, 7 is full block.
_BLOCKS = "▁▂▃▄▅▆▇█"


def signature_bars(seed: str, width: int = 44) -> str:
    """Return a deterministic unicode-block sparkline derived from ``seed``.

    Same seed → same bars (testable); different seed → different fingerprint.
    Used at the top and bottom of the banner so each query renders with its own
    visual signature.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return "".join(_BLOCKS[digest[i % len(digest)] % len(_BLOCKS)] for i in range(width))


def render_banner(console: Console, *, seed: str = "") -> None:
    """Print the Optima banner: signature bar, wordmark, tagline, signature bar."""
    bars = signature_bars(seed or str(time.time_ns()))
    console.print(f"[dim cyan]   {bars}[/]")
    console.print("[bold bright_cyan]   ╔═╗ ╔═╗ ╔╦╗ ╦ ╔╦╗ ╔═╗[/]")
    console.print("[bold bright_cyan]   ║ ║ ╠═╝  ║  ║ ║║║ ╠═╣[/]")
    console.print("[bold bright_cyan]   ╚═╝ ╩    ╩  ╩ ╩ ╩ ╩ ╩[/]")
    console.print("[dim italic]              experiment intelligence[/]")
    console.print(f"[dim cyan]   {bars}[/]")
    console.print()


@contextmanager
def live_status(console: Console, *, enabled: bool) -> Iterator[Callable[[str], None]]:
    """Context manager that yields a ``set_phase(text)`` callback.

    When enabled, drives a rich spinner whose status text is "<phase>  M:SS",
    refreshed every ~100ms by a daemon thread. When disabled (e.g. --json or
    non-TTY), yields a no-op so callers don't have to branch.
    """
    if not enabled:
        yield lambda _phase: None
        return

    state = {"phase": "Starting…"}
    started = time.monotonic()
    status = console.status("", spinner="dots", spinner_style="cyan")
    stop = threading.Event()

    def _tick() -> None:
        while not stop.is_set():
            elapsed = int(time.monotonic() - started)
            mm, ss = divmod(elapsed, 60)
            status.update(f"[cyan]{state['phase']}[/]  [dim]{mm}:{ss:02d}[/]")
            stop.wait(0.1)

    status.start()
    thread = threading.Thread(target=_tick, daemon=True)
    thread.start()
    try:
        yield lambda phase: state.update(phase=phase)
    finally:
        stop.set()
        thread.join(timeout=0.5)
        status.stop()
