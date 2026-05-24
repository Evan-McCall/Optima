"""Optima CLI.

`optima "<query>"`        -> run the experiment-intelligence pipeline
`optima ingest <csv>`     -> normalize a messy experiments CSV into the store

The query is the default command, so a bare `optima "..."` routes to `ask` while
`ingest` still works as a real subcommand.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import click
import typer

from . import config, rendering

console_err = typer.echo


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

    result = run_sync(query, allow_live=not no_live, store_dir=store)
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


def _require_key() -> None:
    try:
        config.require_api_key()
    except RuntimeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
