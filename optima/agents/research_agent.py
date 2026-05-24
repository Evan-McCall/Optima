"""Research Agent (Sonnet): finds relevant published papers via search_papers."""

from __future__ import annotations

from anthropic import AsyncAnthropic

from .. import config
from ..schema import Evidence
from ..tools.registry import ToolRegistry
from .evidence import parse_evidence
from .runner import AgentResult, run_agent


async def gather(
    client: AsyncAnthropic,
    registry: ToolRegistry,
    query: str,
    search_terms: list[str],
) -> tuple[list[Evidence], AgentResult]:
    system = config.load_prompt("research")
    tools = ToolRegistry.schemas_for(["search_papers", "submit_evidence"])
    terms = ", ".join(search_terms) if search_terms else "(derive from the query)"
    user = (
        f"Engineer's query:\n{query}\n\n"
        f"Suggested search terms: {terms}\n\n"
        "Search for the most relevant published papers, then call submit_evidence."
    )
    result = await run_agent(
        client,
        model_key="research",
        system_prompt=system,
        tools=tools,
        user_content=user,
        registry=registry,
        terminal_tool="submit_evidence",
    )
    evidence, dropped = parse_evidence(result.terminal_input)
    if dropped:
        result.notes.append(f"research agent dropped {dropped} malformed evidence item(s)")
    return evidence, result
