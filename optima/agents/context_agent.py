"""Context Agent (Sonnet): mines internal experiments + docs for what worked/failed.

Gets the store's compact index as a cached preamble (cached_suffix), so across its
tool-use loop iterations the tools + system + index prefix is served from cache.
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

from .. import config
from ..schema import Evidence
from ..tools.internal_store import InternalStore
from ..tools.registry import ToolRegistry
from .evidence import parse_evidence
from .runner import AgentResult, run_agent


async def gather(
    client: AsyncAnthropic,
    registry: ToolRegistry,
    store: InternalStore,
    query: str,
    keywords: list[str],
) -> tuple[list[Evidence], AgentResult]:
    system = config.load_prompt("context")
    tools = ToolRegistry.schemas_for(
        ["search_experiments", "get_experiment", "get_doc", "submit_evidence"]
    )
    kw = ", ".join(keywords) if keywords else "(derive from the query)"
    user = (
        f"Engineer's query:\n{query}\n\n"
        f"Focus keywords: {kw}\n\n"
        "Mine the internal history for what worked and what failed, then call submit_evidence."
    )
    result = await run_agent(
        client,
        model_key="context",
        system_prompt=system,
        tools=tools,
        user_content=user,
        registry=registry,
        terminal_tool="submit_evidence",
        cached_suffix=store.compact_index(),
    )
    return parse_evidence(result.terminal_input), result
