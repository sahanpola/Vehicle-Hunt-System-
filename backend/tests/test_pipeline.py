"""Whole pipeline over three simulated days, with fake Tavily, fake LLM and the test database."""
import asyncio
import re

import pytest

from app.agents import availability, condition, parse_request, price, rank, scraper, send_email, value
from app.agents.parse_request import SearchCriteria
from app.db import Report, SearchRequest, SessionLocal, TrackedListing
from app.pipeline import run_search
from tests.conftest import ikman_card

# slug: (title, km, price) per day; a vehicle missing from a day's page is either gone or just not shown
DAYS = {
    1: {"a": ("BMW 320d 2013", 60_000, 16_000_000), "b": ("BMW 320d 2014", 90_000, 15_500_000),
        "c": ("BMW 320d 2012", 120_000, 12_000_000), "d": ("BMW 320d 2011", 200_000, 9_000_000)},
    2: {"a": ("BMW 320d 2013", 60_000, 15_200_000), "c": ("BMW 320d 2012", 120_000, 12_000_000),
        "d": ("BMW 320d 2011", 200_000, 9_000_000), "e": ("BMW 320d 2015", 70_000, 17_000_000)},
    3: {"a": ("BMW 320d 2013", 60_000, 15_200_000), "e": ("BMW 320d 2015", 70_000, 17_000_000)},
}
GONE = {2: {"b"}, 3: set()}


class DayTavily:
    def __init__(self):
        self.day = 1

    def __call__(self, api_key=None):
        return self

    async def extract(self, urls, **kwargs):
        if "/en/ads/" in urls[0]:  # results page
            cards = "".join(ikman_card(slug, *car) for slug, car in DAYS[self.day].items())
            return {"results": [{"url": urls[0], "raw_content": f"{len(DAYS[self.day])} ads\n{cards}"}], "failed_results": []}
        gone = {u for u in urls if u.rsplit("/", 1)[-1] in GONE.get(self.day, set())}
        return {"results": [{"url": u, "raw_content": "ad page"} for u in urls if u not in gone],
                "failed_results": [{"url": u, "error": "Failed to fetch url"} for u in gone]}


@pytest.fixture
def fakes(monkeypatch):
    tavily, llm_calls = DayTavily(), []

    async def ask(system, prompt, output, effort="medium"):
        llm_calls.append(output.__name__)
        ids = re.findall(r'"id": "(L\d+)"', prompt)
        return {
            "SearchCriteria": lambda: SearchCriteria(make="BMW", model="320d", search_query="BMW 320d"),
            "PriceAnalysis": lambda: output(listings=[{"listing_id": i, "price_comment": "ok"} for i in ids], market_summary="m"),
            "ValueAnalysis": lambda: output(listings=[{"listing_id": i, "value_score": 7, "reasoning": "r"} for i in ids]),
            "Ranking": lambda: output(ranked=[{"listing_id": i, "reason": "good"} for i in ids[:3]]),  # sends 3
            "EmailSummary": lambda: output(subject="s", summary="summary"),
        }[output.__name__]()

    monkeypatch.setattr(scraper, "AsyncTavilyClient", tavily)
    monkeypatch.setattr(availability, "AsyncTavilyClient", tavily)
    for module in (parse_request, price, condition, value, rank, send_email):
        monkeypatch.setattr(module, "ask", ask)
    return tavily, llm_calls


def slugs(items):
    return sorted(i["url"].rsplit("/", 1)[-1] for i in items)


def test_three_days_of_reports(fakes):
    tavily, llm_calls = fakes
    with SessionLocal() as db:
        req = SearchRequest(email="a@b.com", vehicle_query="BMW 320d", sites=["https://ikman.lk"], scrape_time="08:00")
        db.add(req)
        db.commit()
        rid = req.id

    reports = []
    for day in (1, 2, 3):
        tavily.day = day
        llm_calls.clear()
        report_id = asyncio.run(run_search(rid))
        with SessionLocal() as db:
            reports.append((db.get(Report, report_id), list(llm_calls)))

    (r1, _), (r2, _), (r3, calls3) = reports
    assert all(r.status == "done" for r, _ in reports)

    assert slugs(r1.top_listings) == ["a", "b", "c"]  # d analysed but not sent

    assert slugs(r2.top_listings) == ["e"]  # d isn't analysed again
    assert slugs(r2.still_available) == ["a", "c"]
    assert next(v for v in r2.still_available if v["url"].endswith("/a"))["price_change"] == -800_000
    assert slugs(r2.unavailable) == ["b"]

    assert r3.top_listings == []
    assert slugs(r3.still_available) == ["a", "c", "e"]  # c not in results but its ad still loads
    assert r3.unavailable == []  # b is only reported once
    assert "PriceAnalysis" not in calls3 and "Ranking" not in calls3  # nothing new, no analysis cost

    with SessionLocal() as db:
        rows = {r.url.rsplit("/", 1)[-1]: r for r in db.query(TrackedListing).filter_by(request_id=rid)}
    assert {k: (r.sent, r.status) for k, r in rows.items()} == {
        "a": (True, "available"), "b": (True, "unavailable"), "c": (True, "available"),
        "d": (False, "available"), "e": (True, "available")}
    assert rows["a"].sent_price == 16_000_000 and rows["a"].last_price == 15_200_000


def test_failed_run_is_recorded(fakes, monkeypatch):
    async def broken(state):
        raise RuntimeError("OpenAI connection error")
    from app.agents import graph as graph_module
    monkeypatch.setattr(graph_module.graph, "ainvoke", lambda *_: broken(None))
    with SessionLocal() as db:
        req = SearchRequest(email="a@b.com", vehicle_query="x", sites=["ikman.lk"], scrape_time="08:00")
        db.add(req)
        db.commit()
    report_id = asyncio.run(run_search(req.id))
    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status == "failed" and "connection error" in report.error
        assert db.query(TrackedListing).filter_by(request_id=req.id).count() == 0
