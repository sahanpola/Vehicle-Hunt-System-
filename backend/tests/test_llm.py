"""llm.ask with a fake OpenAI client (no API calls)."""
import asyncio
from types import SimpleNamespace as NS

import pytest

from app import config
from app.agents import llm
from app.agents.parse_request import SearchCriteria


def fake_client(monkeypatch, response):
    calls = []

    async def parse(**kwargs):
        calls.append(kwargs)
        return response

    monkeypatch.setattr(llm, "_client", NS(responses=NS(parse=parse)))
    return calls


def response(parsed=None, content_type="output_text", status="completed"):
    part = NS(type=content_type, refusal="I can't help with that")
    return NS(output=[NS(type="message", content=[part])], output_parsed=parsed, status=status, incomplete_details=None)


def test_returns_parsed_output(monkeypatch):
    criteria = SearchCriteria(make="BMW", search_query="BMW for sale")
    calls = fake_client(monkeypatch, response(criteria))
    assert asyncio.run(llm.ask("system", "prompt", SearchCriteria)) is criteria
    assert calls[0]["text_format"] is SearchCriteria and calls[0]["instructions"] == "system"


def test_reasoning_effort_only_for_reasoning_models(monkeypatch):
    ok = response(SearchCriteria(make="BMW", search_query="q"))
    calls = fake_client(monkeypatch, ok)
    monkeypatch.setattr(config.get_settings(), "openai_model", "gpt-4o")
    asyncio.run(llm.ask("s", "p", SearchCriteria, effort="low"))
    monkeypatch.setattr(config.get_settings(), "openai_model", "gpt-5")
    asyncio.run(llm.ask("s", "p", SearchCriteria, effort="low"))
    assert "reasoning" not in calls[0]
    assert calls[1]["reasoning"] == {"effort": "low"}


def test_refusal_raises(monkeypatch):
    fake_client(monkeypatch, response(content_type="refusal"))
    with pytest.raises(llm.LLMRefusal):
        asyncio.run(llm.ask("s", "p", SearchCriteria))


def test_missing_output_raises(monkeypatch):
    fake_client(monkeypatch, response(status="incomplete"))
    with pytest.raises(RuntimeError, match="No structured output"):
        asyncio.run(llm.ask("s", "p", SearchCriteria))
