# data/ — your real, private workspace (gitignored)

This is where a real team's **actual experiments and internal documents** live.
Everything in this directory is gitignored **except this README and `.gitkeep`**, so
your private data can never be accidentally committed or pushed.

(The synthetic dataset that ships with the repo lives in
[`../demo_data/`](../demo_data/README.md) and is committed; keep the two separate.)

## Point Optima at this workspace

```bash
# per-run
optima --store data "Help me design my next lean experiment for ..."

# or for the whole session
export OPTIMA_STORE_DIR=data
optima "Help me design my next lean experiment for ..."
```

## How to populate it

Either drop in files matching the canonical schema (see `../demo_data/` for the
exact format)…

```
data/
  experiments.json     # list[Experiment]  — your past experiments
  docs/                # *.md internal reports, postmortems, memos
  papers_cache.json    # optional offline paper fallback
```

…or let Optima normalize a messy CSV export for you:

```bash
optima --store data ingest path/to/your_experiments.csv
# -> writes data/ingested.json (also gitignored)
```

Field definitions for `experiments.json` are in `optima/schema.py` (`Experiment`).
