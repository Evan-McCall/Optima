"""Shared fakes for mocking the Anthropic async client in tests (no key/network)."""

from __future__ import annotations

from types import SimpleNamespace


def usage(**kw) -> SimpleNamespace:
    base = dict(input_tokens=5, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    base.update(kw)
    return SimpleNamespace(**base)


def tool_use(name: str, inp: dict, _id: str = "t1") -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=name, id=_id, input=inp)


def text_block(t: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=t)


def response(blocks, stop: str = "tool_use", **u) -> SimpleNamespace:
    return SimpleNamespace(content=blocks, stop_reason=stop, usage=usage(**u))


class FakeAnthropic:
    """Stands in for AsyncAnthropic. `handler(kwargs) -> response` drives replies."""

    def __init__(self, handler):
        self._handler = handler
        self.messages = _Messages(handler)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Messages:
    def __init__(self, handler):
        self._handler = handler

    async def create(self, **kwargs):
        return self._handler(kwargs)


def factory(handler):
    """Return something callable like AsyncAnthropic(...) that yields a FakeAnthropic."""
    def _make(*args, **kwargs):
        return FakeAnthropic(handler)

    return _make
