"""Optima CLI.

`optima "<query>"`        -> run the experiment-intelligence pipeline
`optima init`             -> first-run setup (industry + API keys)
`optima ingest <csv>`     -> normalize a messy experiments CSV into the store
`optima status`           -> show the current configuration and store contents
`optima experiments`      -> list experiments known to the active store
`optima papers`           -> list cached papers used as the offline fallback

The query is the default command, so a bare `optima "..."` routes to `ask` while
the named subcommands still resolve normally.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
import typer
from rich.console import Console
from rich.table import Table

from . import config, rendering, ui


class _DefaultGroup(typer.core.TyperGroup):
    """Treat a bare `optima "<query>"` as `optima ask "<query>"`.

    Only reroute when the first token isn't a known subcommand, so a genuine usage
    error from a real subcommand (e.g. `optima ingest` with no path) still surfaces
    instead of being misread as a query to `ask`.
    """

    def resolve_command(self, ctx, args):
        if args and not args[0].startswith("-") and args[0] not in self.commands:
            args = ["ask", *args]
        return super().resolve_command(ctx, args)


app = typer.Typer(
    cls=_DefaultGroup,
    add_completion=False,
    no_args_is_help=True,
    help="Optima — experiment intelligence for AI research teams.",
)


@app.command()
def ask(
    query: str = typer.Argument(..., help='Your research question, in quotes.'),
    no_live: bool = typer.Option(False, "--no-live", help="Force the offline paper cache (skip arXiv/Semantic Scholar)."),
    export: Optional[Path] = typer.Option(None, "--export", help="Write the recommendation as markdown to this path."),
    json_out: bool = typer.Option(False, "--json", help="Print the recommendation as JSON instead of rendering it."),
    store: Optional[Path] = typer.Option(None, "--store", help="Store directory (default: demo_data/)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show intent, evidence, and token/cache usage."),
):
    """Ask Optima to design your next experiment."""
    _require_key()
    from .orchestrator import run_sync

    # Banner + spinner go to stderr so they never pollute --json / --export on stdout.
    console = Console(stderr=True)
    if not json_out:
        ui.render_banner(console, seed=query)
    spinner_on = (not json_out) and sys.stderr.isatty()
    with ui.live_status(console, enabled=spinner_on) as set_phase:
        result = run_sync(query, allow_live=not no_live, store_dir=store, progress=set_phase)
    if result.recommendation is None:
        typer.secho("No recommendation produced. " + " ".join(result.notes), fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(1)

    if json_out:
        typer.echo(json.dumps(result.recommendation.model_dump(mode="json"), indent=2))
    else:
        rendering.render(result, verbose=verbose)

    if export:
        Path(export).write_text(rendering.to_markdown(result))
        typer.secho(f"Wrote {export}", fg=typer.colors.GREEN, err=True)


@app.command()
def ingest(
    csv_path: Path = typer.Argument(..., exists=True, readable=True, dir_okay=False, help="CSV of experiments to normalize and add."),
    store: Optional[Path] = typer.Option(None, "--store", help="Store directory to write into (default: demo_data/)."),
):
    """Normalize a messy experiments CSV into the canonical schema and add it to the store."""
    _require_key()
    from .ingest.csv_loader import ingest_csv

    res = asyncio.run(ingest_csv(csv_path, store_dir=store))
    typer.secho(
        f"Ingested {res.parsed}/{res.rows} rows → added {res.added}, updated {res.updated}.",
        fg=typer.colors.GREEN,
    )
    if res.failures:
        typer.secho(f"Failed rows: {', '.join(res.failures)}", fg=typer.colors.YELLOW)
    for e in res.experiments:
        typer.echo(f"  + {e.experiment_id}: {e.hypothesis[:70]}")


@app.command()
def init() -> None:
    """Set up Optima for your team: industry focus + API keys, written to .env."""
    env_path = config._PROJECT_ROOT / ".env"
    current = _parse_env(env_path)

    typer.secho("Welcome to Optima — let's get you set up.\n", fg=typer.colors.CYAN, bold=True)

    # 1. Industry — folded into every paper search so results stay on-domain.
    industry = typer.prompt(
        "What industry or domain does your team work in?\n"
        "  (e.g. legal tech, fintech, healthcare AI — added to every paper search)",
        default=current.get("OPTIMA_INDUSTRY", ""),
        show_default=bool(current.get("OPTIMA_INDUSTRY")),
    ).strip()

    # 2. Anthropic key (required).
    anthropic_key = _prompt_secret("Your Anthropic API key (required)", current.get("ANTHROPIC_API_KEY", ""))
    while not anthropic_key:
        typer.secho("  An Anthropic API key is required to run Optima.", fg=typer.colors.YELLOW)
        anthropic_key = _prompt_secret("Your Anthropic API key (required)", current.get("ANTHROPIC_API_KEY", ""))

    # 3. Semantic Scholar key (optional — Enter to skip).
    s2_key = _prompt_secret(
        "Your Semantic Scholar API key (optional — press Enter to skip)",
        current.get("SEMANTIC_SCHOLAR_API_KEY", ""),
    )

    updates = {"ANTHROPIC_API_KEY": anthropic_key}
    if industry:
        updates["OPTIMA_INDUSTRY"] = industry
    if s2_key:
        updates["SEMANTIC_SCHOLAR_API_KEY"] = s2_key
    _upsert_env(env_path, updates)
    typer.secho(f"\n✓ Saved your settings to {env_path}", fg=typer.colors.GREEN)

    _print_howto(industry)


@app.command()
def status() -> None:
    """Show the active configuration, store contents, and API-key presence."""
    from .tools.internal_store import InternalStore

    store = InternalStore(config.STORE_DIR)
    cache = config.STORE_DIR / "papers_cache.json"
    cached_papers = len(json.loads(cache.read_text())) if cache.exists() else 0

    console = Console()
    console.print("[bold bright_cyan]Optima status[/]")
    console.print(f"  [bold]Industry[/]         {config.INDUSTRY or '[dim](not set — run `optima init`)[/]'}")
    console.print(f"  [bold]Store[/]            {config.STORE_DIR}")
    console.print(f"  [bold]Experiments[/]      {len(store.experiments)}")
    console.print(f"  [bold]Internal docs[/]    {len(store.docs)}")
    console.print(f"  [bold]Cached papers[/]    {cached_papers}")
    console.print(f"  [bold]Anthropic key[/]    {_key_state(config.ANTHROPIC_API_KEY)}")
    console.print(f"  [bold]S2 key[/]           {_key_state(config.SEMANTIC_SCHOLAR_API_KEY)}")
    models = " | ".join(f"{k}={v}" for k, v in config.MODELS.items())
    console.print(f"  [bold]Models[/]           [dim]{models}[/]")


@app.command()
def experiments(
    store: Optional[Path] = typer.Option(None, "--store", help="Store directory (default: demo_data/)."),
    limit: int = typer.Option(25, "--limit", help="Max rows to show."),
) -> None:
    """List experiments known to the active store (curated + ingested, merged)."""
    from .tools.internal_store import InternalStore

    s = InternalStore(store or config.STORE_DIR)
    if not s.experiments:
        typer.secho("No experiments in this store yet. Try `optima ingest <csv>`.", fg=typer.colors.YELLOW)
        return
    table = Table(title=f"Experiments in {s.store_dir} ({len(s.experiments)} total)")
    table.add_column("ID", style="bright_cyan", no_wrap=True)
    table.add_column("Status")
    table.add_column("Task")
    table.add_column("Headline metric")
    table.add_column("$", justify="right")
    for exp in sorted(s.experiments.values(), key=lambda e: e.experiment_id)[:limit]:
        table.add_row(
            exp.experiment_id,
            _status_cell(exp.status),
            exp.task,
            _headline_metric(exp),
            _dollars(exp),
        )
    Console().print(table)


@app.command()
def papers(
    store: Optional[Path] = typer.Option(None, "--store", help="Store directory (default: demo_data/)."),
    limit: int = typer.Option(25, "--limit", help="Max rows to show."),
) -> None:
    """List cached papers used when live arXiv / Semantic Scholar is unavailable."""
    cache_path = (store or config.STORE_DIR) / "papers_cache.json"
    if not cache_path.exists():
        typer.secho(f"No paper cache at {cache_path}.", fg=typer.colors.YELLOW)
        return
    rows = json.loads(cache_path.read_text())
    table = Table(title=f"Cached papers in {cache_path} ({len(rows)} total)")
    table.add_column("ID", style="bright_cyan", no_wrap=True)
    table.add_column("Year", justify="right")
    table.add_column("Title")
    table.add_column("arXiv", style="dim")
    for r in rows[:limit]:
        table.add_row(
            r.get("paper_id", "")[:18],
            str(r.get("year") or "—"),
            (r.get("title") or "").strip(),
            r.get("arxiv_id") or "",
        )
    Console().print(table)


# --- internal helpers shared by status / experiments ------------------------
def _key_state(key: str | None) -> str:
    if not key:
        return "[dim](not set)[/]"
    tail = key[-4:] if len(key) > 4 else "****"
    return f"[green]✓[/] set [dim](…{tail})[/]"


def _status_cell(status_str: str) -> str:
    color = {"success": "green", "failed": "red", "inconclusive": "yellow"}.get(status_str, "white")
    return f"[{color}]{status_str}[/]"


def _headline_metric(exp) -> str:
    """Format the first metric key=value for at-a-glance scanning, or '—'."""
    metrics = exp.metrics
    if isinstance(metrics, dict) and metrics:
        key, value = next(iter(metrics.items()))
        return f"{key}={value}"
    return "—"


def _dollars(exp) -> str:
    d = exp.compute_cost.dollars
    return f"${d:g}" if d is not None else "—"


def _require_key() -> None:
    try:
        config.require_api_key()
    except RuntimeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


def _parse_env(path: Path) -> dict[str, str]:
    """Read KEY=value pairs from a .env file (ignoring comments/blank lines)."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        out[key.strip()] = value.strip()
    return out


def _upsert_env(path: Path, updates: dict[str, str]) -> None:
    """Set each KEY=value in-place if present, else append — preserving the rest
    of the file (comments, ordering, unrelated keys) so we never clobber a .env."""
    lines = path.read_text().splitlines() if path.exists() else []
    remaining = dict(updates)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    lines.extend(f"{key}={value}" for key, value in remaining.items())
    path.write_text("\n".join(lines) + "\n")


def _prompt_secret(label: str, current: str) -> str:
    """Prompt for a secret with input hidden. If one is already set, show a
    masked hint and let the user press Enter to keep it."""
    if current:
        masked = f"…{current[-4:]}" if len(current) > 4 else "set"
        value = typer.prompt(
            f"{label} [{masked} — Enter to keep]",
            default=current, hide_input=True, show_default=False,
        ).strip()
        return value or current
    return typer.prompt(label, default="", hide_input=True, show_default=False).strip()


def _print_howto(industry: str) -> None:
    focus = f" (kept focused on {industry})" if industry else ""
    typer.echo()
    typer.secho("How Optima works", fg=typer.colors.CYAN, bold=True)
    typer.echo(
        "  Upload your team's internal docs and past experiments (as CSVs). Optima\n"
        f"  automatically draws on this company context{focus} and searches the web,\n"
        "  arXiv.org, and semanticscholar.com for relevant research papers — then returns\n"
        "  one cited, compute-lean recommendation for your next experiment. It streamlines\n"
        "  experimentation to shorten iteration cycles and reduce wasted compute.\n"
    )
    typer.secho("Add your team's context", fg=typer.colors.CYAN, bold=True)
    typer.echo(
        "  • Past experiments:  optima ingest path/to/experiments.csv\n"
        "  • Internal docs:     drop .md reports/postmortems into your store's docs/ folder\n"
        "  • Keep private data out of the demo set with:  optima --store data ...\n"
    )
    typer.secho("Ask Optima", fg=typer.colors.CYAN, bold=True)
    typer.echo('  optima "<your question>"')
    typer.secho("  Example:", fg=typer.colors.BRIGHT_BLACK)
    typer.echo(
        '  optima "Our customer support agent is still hallucinating and issuing refunds\n'
        '          without validating first — help me set up my next experiment to\n'
        '          mitigate these hallucinations."\n'
    )


if __name__ == "__main__":
    app()
