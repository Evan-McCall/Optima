"""Shared async tool-use loop for every agent.

One place owns: the cacheable preamble assembly (single `cache_control` breakpoint
at the end of the system block, which caches tools + system together), model-key ->
ID resolution, the tool-execution loop, and usage accounting. Agent modules just
supply a system prompt, a tool subset, the user content, and (optionally) a terminal
tool whose parsed input is returned.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from anthropic import AsyncAnthropic

from .. import config
from ..tools.registry import ToolRegistry


@dataclass
class AgentResult:
    terminal_input: dict | None  # parsed input of the terminal tool, if it was called
    text: str                    # any final assistant text (usually empty for tool-forced agents)
    usage: dict = field(default_factory=lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0})
    iterations: int = 0


async def run_agent(
    client: AsyncAnthropic,
    *,
    model_key: str,
    system_prompt: str,
    tools: list[dict],
    user_content,
    registry: ToolRegistry | None = None,
    terminal_tool: str | None = None,
    force_terminal: bool = False,
    cached_suffix: str = "",
    max_iters: int = 6,
) -> AgentResult:
    """Run the loop until the terminal tool is called, the model stops, or max_iters.

    `system_prompt` + `cached_suffix` form a single cached system block — put stable,
    reusable context (e.g. the experiment index) in `cached_suffix`. Volatile, per-query
    content goes in `user_content` (after the breakpoint), so it never invalidates the cache.
    """
    model = config.model_for(model_key)
    max_tokens = config.max_tokens_for(model_key)

    text = system_prompt + (f"\n\n{cached_suffix}" if cached_suffix else "")
    system = [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
    messages = [{"role": "user", "content": user_content}]

    result = AgentResult(terminal_input=None, text="")

    for i in range(max_iters):
        result.iterations = i + 1
        kwargs = dict(model=model, max_tokens=max_tokens, system=system, tools=tools, messages=messages)
        if force_terminal and terminal_tool:
            kwargs["tool_choice"] = {"type": "tool", "name": terminal_tool}
        resp = await client.messages.create(**kwargs)
        _accumulate(result.usage, resp.usage)

        tool_uses = [b for b in resp.content if b.type == "tool_use"]

        # Terminal tool called -> done.
        for b in tool_uses:
            if terminal_tool and b.name == terminal_tool:
                result.terminal_input = dict(b.input)
                result.text = _text_of(resp.content)
                return result

        # No tools (or model is finished) -> return whatever text we have.
        if resp.stop_reason != "tool_use" or not tool_uses:
            result.text = _text_of(resp.content)
            return result

        # Execute non-terminal (evidence-gathering) tools and feed results back.
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for b in tool_uses:
            if registry is None:
                out = '{"error":"no registry"}'
            else:
                # registry.run may do blocking HTTP (paper search). Run it off the
                # event loop so concurrently-gathered agents don't stall each other.
                out = await asyncio.to_thread(registry.run, b.name, dict(b.input))
            tool_results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
        messages.append({"role": "user", "content": tool_results})

    return result  # exhausted iterations without a terminal call


def _text_of(content) -> str:
    return "".join(b.text for b in content if getattr(b, "type", None) == "text")


def _accumulate(totals: dict, usage) -> None:
    totals["input"] += getattr(usage, "input_tokens", 0) or 0
    totals["output"] += getattr(usage, "output_tokens", 0) or 0
    totals["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
    totals["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0
