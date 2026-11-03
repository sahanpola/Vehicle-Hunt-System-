import asyncio

from app.agents import availability
from tests.conftest import FakeTavily


def view(url):
    return {"key": url, "url": url, "title": url}


def run(state):
    return asyncio.run(availability.check_availability(state))


def test_no_missing_vehicles_means_no_tavily_call(monkeypatch):
    fake = FakeTavily()
    monkeypatch.setattr(availability, "AsyncTavilyClient", fake)
    out = run({"still_listed": [view("a")], "missing": []})
    assert out == {"still_available": [view("a")], "unavailable": []}
    assert fake.calls == []


def test_removed_ads_are_unavailable_and_live_ads_stay(monkeypatch):
    live, failed, removed = "https://ikman.lk/en/ad/live", "https://ikman.lk/en/ad/gone", "https://riyasewana.com/buy/x-1"
    fake = FakeTavily(gone=[failed], removed_text=[removed])
    monkeypatch.setattr(availability, "AsyncTavilyClient", fake)
    out = run({"still_listed": [view("listed")], "missing": [view(live), view(failed), view(removed)]})
    assert [v["url"] for v in out["still_available"]] == ["listed", live]
    assert [v["url"] for v in out["unavailable"]] == [failed, removed]
    assert len(fake.calls) == 1  # one batched call


def test_large_lists_are_batched(monkeypatch):
    fake = FakeTavily()
    monkeypatch.setattr(availability, "AsyncTavilyClient", fake)
    run({"still_listed": [], "missing": [view(f"https://ikman.lk/en/ad/{i}") for i in range(45)]})
    assert [len(c) for c in fake.calls] == [20, 20, 5]


def test_check_error_changes_nothing(monkeypatch):
    monkeypatch.setattr(availability, "AsyncTavilyClient", FakeTavily(error=RuntimeError("network down")))
    out = run({"still_listed": [], "missing": [view("https://ikman.lk/en/ad/a")]})
    assert out == {"still_available": [], "unavailable": []}
