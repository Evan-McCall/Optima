# demo_data/ — synthetic sample dataset (committed)

**This is fake data.** It ships with the repo so Optima runs the moment you clone
it, and so the demo queries have a realistic evidence trail to cite. None of these
experiments, documents, or teams are real.

It is the **default store** (`config.STORE_DIR`), so `optima "<query>"` reads from
here unless you point elsewhere with `--store` / `OPTIMA_STORE_DIR`.

## Contents

| File | What it is |
|------|------------|
| `experiments.json` | 15 synthetic experiments in 3 connected lineages (legal-RAG hallucination eval, support-agent refund hallucinations, fine-tuning method selection on tabular finance). Parent/related links resolve. |
| `papers_cache.json` | ~24 **real** published papers (correct arXiv IDs) used as the offline fallback for paper search. |
| `docs/` | Synthetic internal docs (postmortem, incident report, budget memo) referenced by the experiments. |
| `sample_experiments.csv` | Deliberately messy CSV (odd column names, mixed date formats) for demoing `optima ingest`. |
| `ingested.json` | **Generated, gitignored.** Created when you run `optima ingest`; keeps the curated files above pristine. |

## Using your own data instead

Don't add real experiments or internal documents here — this directory is meant to
stay synthetic and committed. Put real, private data in the gitignored
[`../data/`](../data/README.md) workspace.
