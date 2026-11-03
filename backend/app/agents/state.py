"""Shared state passed between the graph nodes."""
import json
import operator
from typing import Annotated, TypedDict


class Listing(TypedDict):
    """A product record produced by sanitize.py (only the fields the agents need)."""

    id: str  # "L1", "L2", ... assigned by collect
    site: str
    url: str  # the ad's own page, except for "search_page" records (the page they were found on)
    source: str  # "ad" | "card" (results-page card with its own link) | "search_page" | "page"
    title: str
    price_lkr: int | None
    year: int | None
    mileage_km: int | None
    location: str
    details: str  # e.g. "Automatic, Diesel, 2,000 cc, Saloon, Used"
    description: str  # seller's text, trimmed; empty for search-page cards


class PipelineState(TypedDict, total=False):
    # input
    request_id: int
    email: str
    vehicle_query: str
    sites: list[str]
    known: dict[str, dict]  # listing_key -> what earlier runs stored (history.load_known)

    # parse_request
    criteria: dict

    # scrape_site (parallel branches append here)
    raw_listings: Annotated[list[Listing], operator.add]

    # collect
    listings: list[Listing]  # NEW vehicles to analyse (never analysed before for this search)
    found_count: int  # all matching vehicles found today
    still_listed: list[dict]  # sent before and in today's results
    missing: list[dict]  # sent before but not in today's results -> check_availability

    # check_availability
    still_available: list[dict]
    unavailable: list[dict]

    # analysis agents (parallel)
    price: dict  # listing_id -> {price_lkr, year, mileage_km, price_comment} + "_market"
    condition: dict  # listing_id -> {condition_score, highlights, red_flags}
    value: dict  # listing_id -> {value_score, reasoning}

    # rank / send_email
    top_listings: list[dict]
    summary: str
    email_sent: bool
    email_error: str


def listing_key(l: dict) -> str:
    """Stable identity of a vehicle across runs: its ad URL, when the record has one."""
    if l.get("source") == "search_page":  # several records share the search page's URL
        return f"{l['url']}#{l['title'].lower()}|{l.get('price_lkr')}"
    return l["url"].rstrip("/")


PROMPT_FIELDS = ("id", "title", "price_lkr", "year", "mileage_km", "location", "details", "description")


def compact(listing: dict, fields=PROMPT_FIELDS) -> dict:
    """Only the given fields, without empty values."""
    return {k: listing[k] for k in fields if listing.get(k) not in (None, "", [])}


def listings_for_prompt(listings: list[Listing], fields=PROMPT_FIELDS) -> str:
    """One compact JSON object per line (no URLs, no empty fields) to keep prompts small."""
    return "\n".join(json.dumps(compact(l, fields), ensure_ascii=False) for l in listings)
