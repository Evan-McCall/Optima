"""Orchestrates a query: intent pass -> concurrent evidence agents -> synthesis."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from anthropic import AsyncAnthropic

from . import config
from .agents import context_agent, research_agent, synthesis_agent
from .agents.runner import AgentResult, run_agent
from .schema import Evidence, IntentPlan, Recommendation
from .tools.internal_store import InternalStore
from .tools.papers import PaperSearch
from .tools.registry import ToolRegistry


@dataclass
class RunResult:
    recommendation: Recommendation | None
    intent: IntentPlan | None
    research_evidence: list[Evidence] = field(default_factory=list)
    context_evidence: list[Evidence] = field(default_factory=list)
    usage: dict = field(default_factory=lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0})
    notes: list[str] = field(default_factory=list)


async def run(
    query: str,
    *,
    allow_live: bool = True,
    store_dir: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> RunResult:
    config.require_api_key()
    store_dir = store_dir or config.STORE_DIR
    store = InternalStore(store_dir)
    papers = PaperSearch(store_dir, allow_live=allow_live, industry=config.INDUSTRY)
    registry = ToolRegistry(store, papers)

    usage: dict = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    notes: list[str] = []
    notify = progress or (lambda _phase: None)

    async with AsyncAnthropic(api_key=config.require_api_key()) as client:
        # 1. Cheap intent pass (Haiku).
        notify("Reading intent…")
        intent, intent_res = await _intent(client, query)
        _merge(usage, intent_res.usage)
        notes.extend(intent_res.notes)
        if intent is None:
            said = intent_res.text.strip()
            if said and len(said) > 200:
                said = said[:200].rstrip() + "…"
            notes.append(
                "Intent pass returned no usable plan; defaulted to research + context."
                + (f' Model said: "{said}"' if said else "")
            )
        needs_research = intent.needs_research if intent else True
        needs_context = intent.needs_context if intent else True
        terms = intent.search_terms if intent else []

        # 2. Fan out the two evidence agents concurrently (independent prefixes).
        async def _research() -> tuple[list[Evidence], AgentResult | None]:
            if not needs_research:
                return [], None
            return await research_agent.gather(client, registry, query, terms)

        async def _context() -> tuple[list[Evidence], AgentResult | None]:
            if not needs_context:
                return [], None
            return await context_agent.gather(client, registry, store, query, terms)

        notify("Gathering evidence (research + context)…")
        (research_ev, research_res), (context_ev, context_res) = await asyncio.gather(
            _research(), _context()
        )
        if research_res:
            _merge(usage, research_res.usage)
            notes.extend(research_res.notes)
        if context_res:
            _merge(usage, context_res.usage)
            notes.extend(context_res.notes)

        if not research_ev and not context_ev:
            notes.append("No evidence gathered; recommendation may be weak.")

        # 3. Synthesis (forced submit_recommendation + citation firewall).
        notify("Synthesizing recommendation…")
        rec, synth_res = await synthesis_agent.synthesize(client, query, research_ev, context_ev)
        _merge(usage, synth_res.usage)
        notes.extend(synth_res.notes)
        if rec is None:
            notes.append("Synthesis did not return a recommendation.")

    return RunResult(rec, intent, research_ev, context_ev, usage, notes)


def run_sync(
    query: str,
    *,
    allow_live: bool = True,
    store_dir: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> RunResult:
    return asyncio.run(
        run(query, allow_live=allow_live, store_dir=store_dir, progress=progress)
    )


async def _intent(client: AsyncAnthropic, query: str) -> tuple[IntentPlan | None, AgentResult]:
    result = await run_agent(
        client,
        model_key="intent",
        system_prompt=config.load_prompt("intent"),
        tools=ToolRegistry.schemas_for(["record_intent"]),
        user_content=f"Engineer's query:\n{query}",
        terminal_tool="record_intent",
        force_terminal=True,
    )
    if not result.terminal_input:
        return None, result
    try:
        return IntentPlan(**result.terminal_input), result
    except Exception:
        return None, result


def _merge(total: dict, part: dict) -> None:
    for k in total:
        total[k] += part.get(k, 0)
