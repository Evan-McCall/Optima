<div align="center">

```
   ▆▃▇▂▅▆▃█▁▄▇▂▆▃▅▇▁▄▆▃█▂▅▇▃▆▁▄▇▂▅▆▃█▁▄▇▂▆▃▅▇▁
   ╔═╗ ╔═╗ ╔╦╗ ╦ ╔╦╗ ╔═╗
   ║ ║ ╠═╝  ║  ║ ║║║ ╠═╣
   ╚═╝ ╩    ╩  ╩ ╩ ╩ ╩ ╩
              experiment intelligence
   ▆▃▇▂▅▆▃█▁▄▇▂▆▃▅▇▁▄▆▃█▂▅▇▃▆▁▄▇▂▅▆▃█▁▄▇▂▆▃▅▇▁
```

**One cited, compute-lean recommendation for your next experiment — from your terminal.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built with uv](https://img.shields.io/badge/built%20with-uv-de5fe9.svg)](https://docs.astral.sh/uv/)
[![Anthropic Claude](https://img.shields.io/badge/LLM-Claude%204-cb785c.svg)](https://www.anthropic.com)

</div>

You type a research question; a small team of Claude agents pulls relevant **published papers** *and* your team's **own past experiments and docs**, then returns one actionable recommendation — what to try next, why, a concrete experiment spec, and a compute estimate — with per-claim confidence and citations.

> The goal: help AI research teams spend less compute on bad experiments and more time on the experiments that actually move the work forward.

---

## Contents

- [Core concept](#core-concept)
- [Quick start](#quick-start)
- [Commands](#commands)
- [How it works](#how-it-works)
- [Demo walkthrough](#demo-walkthrough)
- [Data layout](#data-layout)
- [Dependencies](#dependencies)
- [Project layout](#project-layout)
- [Design notes](#design-notes)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Core concept

Small/medium AI/ML teams run on tight compute budgets and shared hardware. Redundant or low-signal experiments burn money and lengthen iteration cycles. Optima shortens the path from *hypothesis → validated result* by making sure the next experiment is informed by what's already known — externally **and** internally — instead of rediscovering dead ends.

The four-layer design maps directly onto the code:

| Layer | What it does | Where |
|---|---|---|
| **Company Context** | Internal experiments + docs, canonical schema, relationship-aware | `optima/tools/internal_store.py`, `optima/schema.py` |
| **Knowledge Gathering** | Live arXiv + Semantic Scholar with offline cache fallback | `optima/tools/papers.py` |
| **User Input** | CLI query → cheap intent pass routes to the right agents | `optima/cli.py`, `optima/orchestrator.py` |
| **Output** | Decision summary, ranked evidence, experiment spec, confidence-tagged claims | `optima/rendering.py` |

---

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Evan-McCall/Optima.git
cd Optima
uv sync
uv run optima init           # one-time: industry + API keys
uv run optima "What should my next experiment be for vendor-contract hallucinations?"
```

`optima init` will prompt for your team's industry (appended to every paper search to keep results on-domain), your Anthropic API key, and an optional Semantic Scholar key. Everything writes to a gitignored `.env`.

---

## Commands

| Command | What it does |
|---|---|
| `optima "<query>"` | The main thing — returns one cited, compute-lean recommendation |
| `optima init` | First-run setup: industry + Anthropic key + (optional) Semantic Scholar key |
| `optima ingest <csv>` | Normalize a messy experiments CSV into the canonical schema and add it to the store |
| `optima status` | Show the active configuration, store contents, and API-key presence |
| `optima experiments` | List experiments known to the active store (curated + ingested, merged) |
| `optima papers` | List cached papers used when live arXiv / Semantic Scholar is unavailable |

Useful flags on `optima "<query>"`: `--verbose` (show intent, evidence, token + cache usage), `--no-live` (force the offline cache), `--export <path>` (write the recommendation as markdown), `--json` (machine-readable output), `--store <dir>` (point at a different workspace).

---

## How it works

```
optima "<query>"
        │
        ▼
   ┌─────────────┐   cheap intent pass (Haiku 4.5)
   │ Orchestrator│──────────────────────────────────────────┐
   └─────────────┘                                          │
        │ asyncio.gather (concurrent)                       │
        ├───────────────► Research Agent (Sonnet 4.6) ──► search_papers
        │                   arXiv + Semantic Scholar → local cache fallback
        │                                                   │
        └───────────────► Context Agent (Sonnet 4.6) ──► search/get_experiment, get_doc
                            your internal experiment store  │
                                                            ▼
                                  Synthesis Agent (Sonnet 4.6)
                                  forced submit_recommendation + citation firewall
                                                            │
                                                            ▼
                              ranked, cited recommendation → terminal markdown
```

**Lean compute, by design.** Cheap routing and CSV-row normalization run on **Haiku 4.5**; the reasoning agents (research, context, synthesis) run on **Sonnet 4.6**. The two evidence agents run concurrently. Every model ID lives only in `optima/config.py` (env-overridable), and the context agent caches its stable preamble (tools + system + experiment index) so loop iterations are served from cache.

---

## Demo walkthrough

The bundled `demo_data/` ships with 15 interconnected synthetic experiments across three storylines, each with an open thread the agent can seize. Three canonical queries that exercise the full pipeline:

```bash
# 1. Legal RAG — evaluating / reducing hallucinations
uv run optima "Help me set up my next lean experiment for the vendor contract tool that evaluates for hallucinations." -v

# 2. Support agent — refund hallucinations
uv run optima "Our customer support agent is still hallucinating and issuing refunds without validating first — help me set up my next experiment to mitigate this." -v

# 3. Fine-tuning — method selection on tabular finance data
uv run optima "I'm fine-tuning an open-source model on 2TB of proprietary tabular financial data — what fine-tuning algorithm should I use?" -v
```

Then exercise the ingestion loop — ingest the CSV (whose rows are the *follow-up* experiments) and re-query to see Optima cite the newly added work:

```bash
uv run optima ingest demo_data/sample_experiments.csv
uv run optima "What should my next experiment be for the contract hallucination work?" -v
```

---

## Data layout

Demo data and real data are kept strictly separate:

- **`demo_data/`** — committed synthetic dataset; the default store so a fresh clone runs immediately. Safe to share. ([details](demo_data/README.md))
- **`data/`** — your real, private workspace. Everything in it is **gitignored** except its README/`.gitkeep`, so a team's actual experiments and internal documents can never be committed. ([details](data/README.md))

Point Optima at your private workspace per-run with `--store data` or for a whole session with `export OPTIMA_STORE_DIR=data`.

---

## Dependencies

| Package | Purpose |
|---|---|
| [`anthropic`](https://pypi.org/project/anthropic/) | The only LLM client — Claude API for all five agents |
| [`rich`](https://pypi.org/project/rich/) | Terminal banner, spinner, tables, and markdown rendering |
| [`typer`](https://pypi.org/project/typer/) | CLI framework (subcommands, prompts, help) |
| [`pydantic`](https://pypi.org/project/pydantic/) | Schema validation for `Experiment`, `Paper`, `Recommendation`, … |
| [`httpx`](https://pypi.org/project/httpx/) | Live arXiv / Semantic Scholar HTTP calls |
| [`feedparser`](https://pypi.org/project/feedparser/) | arXiv Atom feed parsing |
| [`python-dotenv`](https://pypi.org/project/python-dotenv/) | Load `.env` for API keys and industry |

---

## Project layout

```
optima/
  config.py            # model IDs, keys, store path, industry, prompt loader
  cli.py               # ask / init / ingest / status / experiments / papers
  orchestrator.py      # intent → concurrent agents → synthesis
  schema.py            # Experiment, Paper, Evidence, ExperimentSpec, Claim, Recommendation
  rendering.py         # Recommendation → terminal markdown / export
  ui.py                # banner, query-seeded sparkline, live spinner
  agents/              # runner (shared loop) + research / context / synthesis
  tools/               # internal_store, papers (live + cache), registry, scoring
  ingest/csv_loader.py # Haiku-powered CSV → canonical schema
prompts/               # agent system prompts (.md)
demo_data/             # synthetic dataset (committed)
data/                  # your private workspace (gitignored contents)
tests/                 # pytest suite (runs with no key/network)
```

---

## Design notes

- **Always-available paper search.** `search_papers` tries live arXiv + Semantic Scholar, then falls back to a curated local cache of ~24 real papers on any failure / 403 / empty result — so the demo never depends on those APIs being reachable. Sources are labeled in the output.
- **Industry-tuned search.** Whatever industry you set in `optima init` is appended to every paper query at the wire level (live *and* cache), so results stay on-domain regardless of what terms the agent picks.
- **Citation firewall.** The synthesis agent is *forced* to emit a structured recommendation, and a post-validation guard in `synthesis_agent.py` drops any citation pointing at an ID that wasn't actually in the gathered evidence — a hallucinated reference can't reach the output.
- **Heuristic estimates.** Compute / cost / savings figures are model estimates derived from experiment metadata, surfaced as estimates, not measurements.
- **No vector DB.** The corpus is small (tens of records); the context agent gets a compact in-context index plus keyword search/get tools and lets Claude judge relevance.

---

## Roadmap

- **Data-source connectors:** Weights & Biases, git repos, and Google Drive auto-ingest into the Company Context Layer (currently CSV/JSON only).
- **Tutor / persona layer:** follow-up Q&A on a returned recommendation (interactive refinement instead of one-shot).
- **Richer export formats:** HTML and PDF in addition to terminal markdown.
- **Post-recommendation eval hooks:** track which recommendations actually got run and how they performed.
- **Embeddings + vector retrieval:** once a team's store grows past hundreds of experiments, layer it in alongside the existing keyword tools.

---

## Contributing

```bash
uv run pytest
```

The suite mocks the Anthropic client and simulates paper-API failure, so it passes with **no API key and no network**. Please add a test for any new tool, agent, or CLI command. The canonical record shape lives in `optima/schema.py` — keep changes there backwards-compatible (the store loads `ingested.json` *on top of* `experiments.json`).

---

## License

MIT — see [`LICENSE`](LICENSE).
