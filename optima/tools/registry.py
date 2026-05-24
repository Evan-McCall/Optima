"""Anthropic tool schemas + name->callable dispatch.

`SUBMIT_RECOMMENDATION` is the forced-output tool for the synthesis agent (see
schema.py — the Recommendation models mirror it exactly). The rest are the
evidence-gathering tools the research/context agents call in their loops.
"""

from __future__ import annotations

import json

from .internal_store import InternalStore
from .papers import PaperSearch

# -- evidence-gathering tool schemas -----------------------------------------
SEARCH_PAPERS = {
    "name": "search_papers",
    "description": (
        "Search published research (arXiv + Semantic Scholar, with a local cache "
        "fallback) for papers relevant to a hypothesis or method. Returns titles, "
        "abstracts, authors, year, citation counts, and IDs."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Focused search query, e.g. 'reduce RAG hallucination faithfulness evaluation'.",
            },
            "max_results": {
                "type": "integer",
                "description": "Max papers to return (default 6).",
            },
        },
        "required": ["query"],
    },
}

SEARCH_EXPERIMENTS = {
    "name": "search_experiments",
    "description": (
        "Search the team's internal past experiments by keyword/topic. Returns "
        "matching experiments with hypothesis, method, metrics, status, cost, "
        "conclusion, and their parent/related experiment links."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "string",
                "description": "Topic/keywords, e.g. 'hallucination refund validation agent'.",
            },
            "limit": {"type": "integer", "description": "Max experiments (default 8)."},
        },
        "required": ["keywords"],
    },
}

GET_EXPERIMENT = {
    "name": "get_experiment",
    "description": "Fetch one internal experiment in full by its experiment_id (e.g. 'exp_004').",
    "input_schema": {
        "type": "object",
        "properties": {"experiment_id": {"type": "string"}},
        "required": ["experiment_id"],
    },
}

GET_DOC = {
    "name": "get_doc",
    "description": "Fetch an internal document (postmortem, incident report, memo) in full by name.",
    "input_schema": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Doc name, e.g. 'rag_eval_postmortem'."}},
        "required": ["name"],
    },
}

# -- forced synthesis output tool --------------------------------------------
SUBMIT_RECOMMENDATION = {
    "name": "submit_recommendation",
    "description": (
        "Submit the final experiment recommendation to the user. You MUST use this "
        "tool to output your synthesized conclusion. Do not include conversational "
        "text before or after calling this tool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "decision_summary": {
                "type": "string",
                "description": "About 4 concise sentences (3-5 acceptable) covering exactly what to try next, why it is promising based on the gathered evidence, and what pitfalls to avoid. Be terse.",
            },
            "ranked_evidence": {
                "type": "array",
                "description": "About 6 items (5-7 max) — the most decisive evidence supporting the recommendation, from both internal experiments and external papers, most decisive first.",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ["internal_experiment", "external_paper", "internal_doc"],
                        },
                        "title": {"type": "string"},
                        "why_relevant": {
                            "type": "string",
                            "description": "1-2 sentences on why this evidence is critical to the recommendation.",
                        },
                        "ref_id": {
                            "type": "string",
                            "description": "The experiment_id, arxiv_id/paper_id, or document name for citation linkage.",
                        },
                    },
                    "required": ["kind", "title", "why_relevant", "ref_id"],
                },
            },
            "experiment_spec": {
                "type": "object",
                "description": "Concrete, actionable configuration for the suggested experiment.",
                "properties": {
                    "model": {"type": "string", "description": "Recommended base model (e.g. Llama-3-8B, Claude Sonnet 4.5)."},
                    "method": {"type": "string", "description": "The core methodology to employ."},
                    "key_hyperparams": {"type": "string", "description": "Specific hyperparameter suggestions."},
                    "estimated_compute_cost": {"type": "string", "description": "Heuristic cost estimate, e.g. '$50-$100' or '16 A100 hours'."},
                    "estimated_savings_vs_naive": {"type": "string", "description": "How much compute/time is saved vs a brute-force approach."},
                },
                "required": ["model", "method", "key_hyperparams", "estimated_compute_cost", "estimated_savings_vs_naive"],
            },
            "claims": {
                "type": "array",
                "description": "About 6 factual claims (ideally one per ranked_evidence item) from the summary/spec, each backed by a citation_ref pointing at a ref_id in ranked_evidence.",
                "items": {
                    "type": "object",
                    "properties": {
                        "statement": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["High", "Medium", "Low"]},
                        "citation_ref": {"type": "string", "description": "The ref_id (experiment or paper ID) supporting this statement."},
                    },
                    "required": ["statement", "confidence", "citation_ref"],
                },
            },
        },
        "required": ["decision_summary", "ranked_evidence", "experiment_spec", "claims"],
    },
}

# -- terminal tools for the routing + evidence agents ------------------------
RECORD_INTENT = {
    "name": "record_intent",
    "description": "Record the routing decision for the engineer's query. You MUST call this and nothing else.",
    "input_schema": {
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Technical area, e.g. 'rag/retrieval', 'agents/tool-use', 'fine-tuning', 'evaluation/hallucination', 'other'."},
            "goal": {"type": "string", "description": "One sentence: what the engineer wants to achieve next."},
            "needs_research": {"type": "boolean", "description": "Whether published-paper search would help (usually true)."},
            "needs_context": {"type": "boolean", "description": "Whether the team's own past experiments/docs are relevant (usually true)."},
            "search_terms": {"type": "array", "items": {"type": "string"}, "description": "3-6 concise paper-search phrases."},
        },
        "required": ["domain", "goal", "needs_research", "needs_context", "search_terms"],
    },
}

SUBMIT_EVIDENCE = {
    "name": "submit_evidence",
    "description": "Submit your ranked evidence for this query. You MUST finish by calling this tool.",
    "input_schema": {
        "type": "object",
        "properties": {
            "evidence": {
                "type": "array",
                "description": "3-6 ranked evidence items, most decisive first.",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["internal_experiment", "external_paper", "internal_doc"]},
                        "title": {"type": "string"},
                        "ref_id": {"type": "string", "description": "Exact experiment_id, arxiv_id/paper_id, or document name. Never invent."},
                        "why_relevant": {"type": "string", "description": "1-2 sentences tying this to the engineer's goal."},
                    },
                    "required": ["kind", "title", "ref_id", "why_relevant"],
                },
            }
        },
        "required": ["evidence"],
    },
}

_ALL_SCHEMAS = {
    s["name"]: s
    for s in (
        SEARCH_PAPERS, SEARCH_EXPERIMENTS, GET_EXPERIMENT, GET_DOC,
        RECORD_INTENT, SUBMIT_EVIDENCE, SUBMIT_RECOMMENDATION,
    )
}


class ToolRegistry:
    """Holds the live store + paper searcher and dispatches tool calls to them."""

    def __init__(self, store: InternalStore, paper_search: PaperSearch):
        self.store = store
        self.paper_search = paper_search
        self._handlers = {
            "search_papers": self._search_papers,
            "search_experiments": self._search_experiments,
            "get_experiment": self._get_experiment,
            "get_doc": self._get_doc,
        }

    @staticmethod
    def schemas_for(names: list[str]) -> list[dict]:
        return [_ALL_SCHEMAS[n] for n in names]

    def run(self, name: str, tool_input: dict) -> str:
        handler = self._handlers.get(name)
        if handler is None:
            return json.dumps({"error": f"unknown tool {name!r}"})
        try:
            return handler(tool_input)
        except Exception as exc:  # surface errors to the model rather than crashing
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})

    # -- handlers (return JSON strings for tool_result content) --------------
    def _search_papers(self, args: dict) -> str:
        papers = self.paper_search.search(args["query"], int(args.get("max_results", 6)))
        return json.dumps([_paper_view(p) for p in papers])

    def _search_experiments(self, args: dict) -> str:
        exps = self.store.search_experiments(args["keywords"], int(args.get("limit", 8)))
        return json.dumps([e.model_dump(mode="json") for e in exps])

    def _get_experiment(self, args: dict) -> str:
        exp = self.store.get_experiment(args["experiment_id"])
        return json.dumps(exp.model_dump(mode="json") if exp else {"error": "not found"})

    def _get_doc(self, args: dict) -> str:
        doc = self.store.get_doc(args["name"])
        return json.dumps(doc.model_dump(mode="json") if doc else {"error": "not found"})


def _paper_view(p) -> dict:
    """Trim paper fields to what the agent needs (keeps tool_result tokens lean)."""
    return {
        "paper_id": p.paper_id,
        "arxiv_id": p.arxiv_id,
        "title": p.title,
        "authors": p.authors[:6],
        "year": p.year,
        "citation_count": p.citation_count,
        "abstract": p.abstract,
        "url": p.url,
        "source": p.source,
    }
