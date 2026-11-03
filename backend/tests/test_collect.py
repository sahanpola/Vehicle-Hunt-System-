import asyncio

from app.agents.collect import collect
from app.agents.state import listing_key
from tests.conftest import listing

CRITERIA = {"make": "BMW"}


def known_entry(url, sent=True, status="available", sent_price=16_000_000):
    return {"url": url, "sent": sent, "status": status, "sent_price": sent_price, "last_price": sent_price,
            "sent_at": "2026-10-20T08:00:00", "data": {"title": "BMW 320d 2013", "site": "ikman.lk", "url": url}}


def run(raw, known=None):
    return asyncio.run(collect({"raw_listings": raw, "criteria": CRITERIA, "known": known or {}}))


def test_splits_new_still_listed_and_missing():
    a, b, c, d = (f"https://ikman.lk/en/ad/{x}" for x in "abcd")
    raw = [listing(url=a, price=15_200_000), listing(url=b, km=1), listing(url=d, km=2)]
    known = {
        a: known_entry(a),                      # sent, still listed (price dropped)
        c: known_entry(c),                      # sent, missing today
        d: known_entry(d, sent=False),          # analysed but not sent: skipped
        "x": known_entry("x", status="unavailable"),  # already reported gone: ignored
    }
    out = run(raw, known)
    assert [l["url"] for l in out["listings"]] == [b]  # only the never-seen vehicle is analysed
    assert out["listings"][0]["id"] == "L1"
    assert [v["url"] for v in out["still_listed"]] == [a]
    assert out["still_listed"][0]["price_change"] == -800_000
    assert [v["url"] for v in out["missing"]] == [c]
    assert out["found_count"] == 3


def test_drops_duplicates_and_caps_with_sites_interleaved(monkeypatch):
    from app import config
    monkeypatch.setattr(config.get_settings(), "max_listings_to_analyse", 6)
    raw = [listing(url=f"r{i}", site="riyasewana.com", price=1_000_000 + i, km=10_000 + i) for i in range(10)]
    raw += [listing(url=f"i{i}", site="ikman.lk", price=2_000_000 + i, km=20_000 + i) for i in range(3)]
    raw.append(listing(url="r0-again", site="riyasewana.com", price=1_000_000, km=10_000))  # same vehicle as r0
    out = run(raw)
    assert out["found_count"] == 13
    assert [l["site"][0] for l in out["listings"]] == ["r", "i", "r", "i", "r", "i"]


def test_listing_key_uses_ad_url():
    assert listing_key(listing(url="https://ikman.lk/en/ad/a/")) == "https://ikman.lk/en/ad/a"
    page = listing(url="https://ikman.lk/en/ads/x", source="search_page", title="BMW 320d", price=5)
    assert listing_key(page) == "https://ikman.lk/en/ads/x#bmw 320d|5"
