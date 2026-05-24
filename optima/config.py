"""Central configuration: model IDs, API keys, store location.

Every model string lives ONLY here so we can hot-swap a model (rate limits, a
changed date-string tag) in one place — or via an env var — without touching any
agent code. See plan: "Model-ID resilience".
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Model IDs (override individually via env) -------------------------------
# Tiered for "lean compute": cheap routing/ingest on Haiku, reasoning on Sonnet.
MODELS: dict[str, str] = {
    "intent": os.getenv("OPTIMA_MODEL_INTENT", "claude-haiku-4-5-20251001"),
    "ingest": os.getenv("OPTIMA_MODEL_INGEST", "claude-haiku-4-5-20251001"),
    "research": os.getenv("OPTIMA_MODEL_RESEARCH", "claude-sonnet-4-6"),
    "context": os.getenv("OPTIMA_MODEL_CONTEXT", "claude-sonnet-4-6"),
    "synthesis": os.getenv("OPTIMA_MODEL_SYNTHESIS", "claude-sonnet-4-6"),
}

# Per-agent max output tokens.
MAX_TOKENS: dict[str, int] = {
    "intent": 1024,
    "ingest": 1024,
    "research": 4096,
    "context": 4096,
    "synthesis": 4096,
}


def model_for(key: str) -> str:
    """Resolve a logical agent key (e.g. "research") to a concrete model ID."""
    try:
        return MODELS[key]
    except KeyError as exc:  # pragma: no cover - guards typos
        raise KeyError(
            f"Unknown model key {key!r}; expected one of {sorted(MODELS)}"
        ) from exc


def max_tokens_for(key: str) -> int:
    return MAX_TOKENS.get(key, 4096)


# --- Secrets ----------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")

# --- Store location ---------------------------------------------------------
# Default = the committed synthetic dataset (demo_data/) so a fresh clone runs
# immediately. Point at your real, private workspace with OPTIMA_STORE_DIR or
# the CLI `--store` flag (e.g. the gitignored data/ dir). See data/README.md.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_STORE = _PROJECT_ROOT / "demo_data"
STORE_DIR = Path(os.getenv("OPTIMA_STORE_DIR", str(_DEFAULT_STORE)))

# --- Agent system prompts ---------------------------------------------------
PROMPTS_DIR = _PROJECT_ROOT / "prompts"


def load_prompt(name: str) -> str:
    """Load an agent system prompt (e.g. 'research') from prompts/<name>.md."""
    return (PROMPTS_DIR / f"{name}.md").read_text().strip()


def require_api_key() -> str:
    """Return the Anthropic key or raise a clear, actionable error."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it (or add it to a .env file) "
            "before running queries or ingestion:\n\n"
            "    export ANTHROPIC_API_KEY=sk-ant-...\n"
        )
    return ANTHROPIC_API_KEY
