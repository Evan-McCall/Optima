# Optima

**An experiment intelligence layer for AI research teams.** Optima connects published research, internal experiment history, and prior results to reduce redundant experimentation and speed up iteration.

You type a question in your terminal; a small team of Claude agents pulls the relevant published papers **and** your team's own past experiments/docs, then returns **one actionable recommendation** — what to try next, why, a concrete experiment spec, and a compute estimate — with per-claim confidence and citations.

> The goal: help AI research teams spend less compute on bad experiments and more time on the experiments that actually move the work forward.

---

## Why

Small/medium AI/ML teams run on tight compute budgets and shared hardware. Redundant or low-signal experiments burn money and lengthen iteration cycles. Optima shortens the path from hypothesis → validated result by making sure the next experiment is informed by what's already known — externally and internally — instead of rediscovering dead ends.

## How it works

```
optima "<query>"
        │
        ▼
   ┌─────────────┐   cheap intent pass (Haiku 4.5)
   │ Orchestrator│──────────────────────────────────────────┐
   └─────────────┘                                           │
        │ asyncio.gather (concurrent)                        │
        ├───────────────► Research Agent (Sonnet 4.6) ──► search_papers
        │                   arXiv + Semantic Scholar → local cache fallback
        │                                                    │
        └───────────────► Context Agent (Sonnet 4.6) ──► search/get_experiment, get_doc
                            your internal experiment store   │
                                                             ▼
                                  Synthesis Agent (Sonnet 4.6)
                                  forced submit_recommendation + citation firewall
                                                             │
                                                             ▼
                              ranked, cited recommendation → terminal markdown
```

The four layers from the design map directly onto the code:

| Layer | What it does | Where |
|---|---|---|
| **Company Context** | Makes internal experiments/docs machine-readable; canonical schema with relationships | `optima/tools/internal_store.py`, `optima/schema.py` |
| **Knowledge Gathering** | Published-research search (arXiv + Semantic Scholar) with offline cache fallback | `optima/tools/papers.py` |
| **User Input** | CLI query → cheap intent pass routes to the right agents | `optima/cli.py`, `optima/orchestrator.py` |
| **Output** | Decision summary, ranked evidence, experiment spec, confidence-tagged claims | `optima/rendering.py` |

**Lean compute, by design:** cheap routing and CSV-row normalization run on **Haiku 4.5**; the reasoning agents (research, context, synthesis) run on **Sonnet 4.6**. The two evidence agents run concurrently. Every model ID lives only in `optima/config.py` (override via env), and the context agent caches its stable preamble (tools + system + experiment index) so loop iterations are served from cache.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Clone, then:

```bash
git clone https://github.com/Evan-McCall/Optima.git
cd Optima
uv sync
```

## Configure

Optima only calls the Anthropic API. Set your key (a Semantic Scholar key is optional — it just raises live paper-search rate limits):

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

`.env` is gitignored. You can also `export ANTHROPIC_API_KEY=...` instead.

## Usage

```bash
# Ask Optima to design your next experiment (reads the demo dataset by default)
uv run optima "Help me set up my next lean experiment for the vendor contract tool that evaluates for hallucinations."

# Show the agents' work: intent, evidence gathered, token + cache usage
uv run optima "..." --verbose

# Force the offline paper cache (no arXiv/Semantic Scholar calls)
uv run optima "..." --no-live

# Export the recommendation as markdown, or print JSON
uv run optima "..." --export rec.md
uv run optima "..." --json

# Normalize a messy experiments CSV into the canonical schema and add it to the store
uv run optima ingest demo_data/sample_experiments.csv
```

Point Optima at your **own** private data with `--store data` or `OPTIMA_STORE_DIR=data` (see [Data layout](#data-layout)).

## Demo script

The bundled `demo_data/` has 15 interconnected synthetic experiments across three storylines, each with an open thread the agent can seize. Try the canonical queries:

```bash
# 1. Legal RAG — evaluating/reducing hallucinations
uv run optima "Help me set up my next lean experiment for the vendor contract tool that evaluates for hallucinations." -v

# 2. Support agent — refund hallucinations
uv run optima "Our customer support agent is still hallucinating and issuing refunds without validating first — help me set up my next experiment to mitigate this." -v

# 3. Fine-tuning — method selection on tabular finance data
uv run optima "I'm fine-tuning an open-source model on 2TB of proprietary tabular financial data — what fine-tuning algorithm should I use?" -v
```

Then show the ingestion loop — ingest the messy CSV (whose rows are the *follow-up* experiments) and re-query to see Optima cite the newly added work:

```bash
uv run optima ingest demo_data/sample_experiments.csv
uv run optima "What should my next experiment be for the contract hallucination work?" -v
```

## Data layout

Demo data and real data are kept strictly separate:

- **`demo_data/`** — committed, synthetic dataset; the default store so a fresh clone runs immediately. Safe to share. ([details](demo_data/README.md))
- **`data/`** — your real, private workspace. **Everything in it is gitignored** except its README/`.gitkeep`, so a team's actual experiments and internal documents can never be committed. ([details](data/README.md))

## Project layout

```
optima/
  config.py            # model IDs, keys, store path, prompt loader
  cli.py               # `optima "<query>"` and `optima ingest <csv>`
  orchestrator.py      # intent → concurrent agents → synthesis
  schema.py            # Experiment, Paper, Evidence, ExperimentSpec, Claim, Recommendation
  rendering.py         # Recommendation → terminal markdown / export
  agents/              # runner (shared loop) + research / context / synthesis
  tools/               # internal_store, papers (live + cache), registry, scoring
  ingest/csv_loader.py # Haiku-powered CSV → canonical schema
prompts/               # agent system prompts (.md)
demo_data/             # synthetic dataset (committed)
data/                  # your private workspace (gitignored contents)
tests/                 # pytest suite (runs with no key/network)
```

## Design notes

- **Always-available paper search.** `search_papers` tries live arXiv + Semantic Scholar, then falls back to a curated local cache of ~24 real papers on any failure/403/empty result — so the demo never depends on those APIs being reachable. Sources are labeled.
- **Citation firewall.** The synthesis agent is *forced* to emit a structured recommendation, and a post-validation guard in `synthesis_agent.py` drops any citation pointing at an ID that wasn't actually in the gathered evidence — a hallucinated reference can't reach the output.
- **Heuristic estimates.** Compute/cost/savings figures are model estimates derived from experiment metadata, surfaced as estimates, not measurements.
- **No vector DB.** The corpus is small (tens of records); the context agent gets a compact in-context index plus keyword search/get tools and lets Claude judge relevance.

## Testing

```bash
uv run pytest
```

The suite mocks the Anthropic client and simulates paper-API failure, so it passes with **no API key and no network**.

## Non-goals (hackathon scope)

W&B / git / Google Drive connectors are stubbed-out interfaces only; embeddings/vector search and a web UI are out of scope for now.
