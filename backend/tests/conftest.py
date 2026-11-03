"""Test setup: no test may call OpenAI, Tavily or SMTP for real (they cost money / send mail).

Env vars are set before the app is imported, so tests never read real keys from .env and
use a throwaway SQLite file.
"""
import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="vehicle-agent-tests-")
os.environ.update(
    OPENAI_API_KEY="test-key",
    OPENAI_MODEL="gpt-4o",
    TAVILY_API_KEY="test-key",
    SMTP_USER="",
    SMTP_PASSWORD="",
    EMAIL_FROM="",
    DATABASE_URL=f"sqlite:///{_tmp}/test.db",
    MAX_PAGES_PER_SITE="2",
    MAX_LISTINGS_TO_ANALYSE="25",
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.agents import availability, llm, scraper  # noqa: E402
from app.db import init_db  # noqa: E402

init_db()


class _NoNetwork:
    def __init__(self, *args, **kwargs):
        raise AssertionError("Tests must not use the real Tavily client: patch it with a fake.")


class _NoLLM:
    def __getattr__(self, name):
        raise AssertionError("Tests must not call the real OpenAI API: patch `ask` with a fake.")


@pytest.fixture(autouse=True)
def block_paid_apis(monkeypatch):
    monkeypatch.setattr(scraper, "AsyncTavilyClient", _NoNetwork)
    monkeypatch.setattr(availability, "AsyncTavilyClient", _NoNetwork)
    monkeypatch.setattr(llm, "_client", _NoLLM())


# ---------- shared helpers ----------

def listing(url="https://ikman.lk/en/ad/a", site="ikman.lk", title="BMW 320d 2013", price=16_000_000,
            year=2013, km=60_000, source="card", **extra) -> dict:
    return {"id": "", "site": site, "url": url, "source": source, "title": title, "price_lkr": price,
            "year": year, "mileage_km": km, "location": "Colombo", "details": "", "description": "", **extra}


def ikman_card(slug, title, km, price, attrs="Saloon | Used", category="Cars") -> str:
    """One ikman results-page card, as Tavily extract returns it in markdown."""
    return (f'\n*   [![Image 1: {title}](https://i.ikman-st.com/x.jpg) ## {title} {km:,} km | {attrs} '
            f'Colombo, {category} Rs {price:,}](https://ikman.lk/en/ad/{slug} "{title} for sale")')


def riya_card(ad_id, title, price, year, loc="Homagama", km=None, vtype="Car", extra="") -> str:
    """One riyasewana results-page card in markdown."""
    url = f"https://riyasewana.com/buy/{ad_id}"
    km_part = f"·{km:,} km" if km else ""
    return (f'\n*   [![Image 11: {title} {year} {vtype}](https://riyasewana.com/thumb/x.jpg)]({url} "{title} {year} {vtype}") '
            f'[{title} {vtype}]({url} "{title} {year} {vtype}") {price} {year} {loc}{km_part} {extra}3h ago')


class FakeTavily:
    """Stand-in for AsyncTavilyClient. `pages` maps URL substrings to markdown; `gone` lists ad URLs that fail."""

    def __init__(self, pages=None, gone=(), removed_text=(), error=None):
        self.pages, self.gone, self.removed_text, self.error = pages or {}, set(gone), set(removed_text), error
        self.calls = []

    def __call__(self, api_key=None):  # used as the class: AsyncTavilyClient(api_key=...)
        return self

    async def extract(self, urls, **kwargs):
        self.calls.append(list(urls))
        if self.error:
            raise self.error
        results, failed = [], []
        for url in urls:
            if url in self.gone:
                failed.append({"url": url, "error": "Failed to fetch url"})
            elif url in self.removed_text:
                results.append({"url": url, "raw_content": "# This ad is no longer available"})
            else:
                md = next((v for k, v in self.pages.items() if k in url), "an ad page")
                results.append({"url": url, "raw_content": md})
        return {"results": results, "failed_results": failed}

    async def search(self, **kwargs):
        self.calls.append(["search", kwargs.get("query")])
        return {"results": []}
