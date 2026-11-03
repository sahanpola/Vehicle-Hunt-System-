"""LLM agents with `ask` faked: checks what each agent sends and how it uses the answer."""
import asyncio

from app.agents import condition, price, rank, send_email
from app.agents.rank import Ranking
from tests.conftest import listing


def fake_ask(answer, calls):
    async def ask(system, prompt, output, effort="medium"):
        calls.append({"prompt": prompt, "output": output.__name__, "effort": effort})
        return answer(output) if callable(answer) else answer
    return ask


def test_rank_skips_unknown_and_repeated_ids(monkeypatch):
    calls = []
    monkeypatch.setattr(rank, "ask", fake_ask(
        Ranking(ranked=[{"listing_id": i, "reason": i} for i in ["L3", "L1", "L3", "L9", "L2"]]), calls))
    items = [{**listing(url=f"u{i}"), "id": f"L{i}"} for i in (1, 2, 3)]
    out = asyncio.run(rank.rank({"listings": items, "vehicle_query": "q", "price": {"L1": {"price_comment": "cheap"}}}))
    assert [(t["rank"], t["id"]) for t in out["top_listings"]] == [(1, "L3"), (2, "L1"), (3, "L2")]
    assert out["top_listings"][1]["price_comment"] == "cheap"
    assert "url" not in calls[0]["prompt"] and "u1" not in calls[0]["prompt"]  # URLs aren't sent to the LLM


def test_empty_listings_make_no_llm_calls(monkeypatch):
    calls = []
    for module in (price, rank, condition):
        monkeypatch.setattr(module, "ask", fake_ask(None, calls))
    state = {"listings": [], "criteria": {}, "vehicle_query": "q"}
    assert asyncio.run(price.price(state)) == {"price": {}}
    assert asyncio.run(rank.rank(state)) == {"top_listings": []}
    assert asyncio.run(condition.condition(state)) == {"condition": {}}
    assert calls == []


def test_condition_only_calls_llm_for_listings_with_description(monkeypatch):
    calls = []
    monkeypatch.setattr(condition, "ask", fake_ask(
        lambda out: out(condition_score=8, highlights=["one owner"], red_flags=[]), calls))
    items = [{**listing(url="a", description="One owner, full service history"), "id": "L1"},
             {**listing(url="b"), "id": "L2"}]
    out = asyncio.run(condition.condition({"listings": items}))["condition"]
    assert out["L1"]["condition_score"] == 8
    assert out["L2"] == condition.NO_DETAILS
    assert len(calls) == 1 and calls[0]["effort"] == "low"


def test_email_without_changes_skips_llm(monkeypatch):
    calls = []
    monkeypatch.setattr(send_email, "ask", fake_ask(None, calls))
    out = asyncio.run(send_email.send_email({"email": "a@b.com", "vehicle_query": "BMW",
                                             "top_listings": [], "still_available": [{"title": "x"}], "unavailable": []}))
    assert calls == [] and out["email_sent"] is False
    assert "1 from earlier emails are still available" in out["summary"]


def test_email_html_has_three_sections():
    top = [{**listing(url="https://ikman.lk/en/ad/n"), "rank": 1, "rank_reason": "best"}]
    still = [{**listing(url="https://ikman.lk/en/ad/s"), "price_change": -500_000, "sent_at": "2026-10-20T08:00:00"}]
    gone = [{**listing(url="https://ikman.lk/en/ad/g"), "sent_at": "2026-10-19T08:00:00"}]
    body = send_email._html("summary", top, still, gone)
    assert "New today (1)" in body and "Still available from earlier emails (1)" in body and "No longer available (1)" in body
    assert "▼ Rs. 500,000 since sent" in body
