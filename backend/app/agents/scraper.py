"""scrape_site (plain Python): fetch one site's listings with Tavily, keep only product records.

Sites with a URL builder (sites.py): open the site's own search-results URL with the
buyer's filters via Tavily extract, then parse each car card. Other sites, or if that
returns nothing: Tavily web search restricted to the site's domain.
"""
import logging
from urllib.parse import urlparse

from tavily import AsyncTavilyClient

from app.agents.sanitize import extract_listings, parse_results_page
from app.agents.sites import SEARCH_URLS
from app.agents.state import Listing
from app.config import get_settings

log = logging.getLogger(__name__)


def domain_of(site: str) -> str:
    """'https://ikman.lk/en/ads/...' -> 'ikman.lk'"""
    netloc = urlparse(site if "://" in site else f"https://{site}").netloc
    return netloc.removeprefix("www.")


async def _fetch_markdown(client: AsyncTavilyClient, url: str) -> str | None:
    # "advanced" is needed: basic extraction drops the cards' prices and links.
    result = await client.extract(urls=[url], format="markdown", extract_depth="advanced")
    pages = result.get("results") or []
    return pages[0]["raw_content"] if pages else None


async def _from_site_search(client: AsyncTavilyClient, site: str, criteria: dict) -> list[Listing]:
    build = SEARCH_URLS[site]
    max_pages = get_settings().max_pages_per_site

    # Try each candidate URL (e.g. make+model, then make only) until one returns cars.
    for candidate in range(len(build(criteria))):
        listings: list[Listing] = []
        for page in range(1, max_pages + 1):
            url = build(criteria, page)[candidate]
            markdown = await _fetch_markdown(client, url)
            cards, total = parse_results_page(site, markdown or "")
            log.info("%s page %d: %d cards (site total %s) %s", site, page, len(cards), total, url)
            listings += cards
            if not cards or not total or len(listings) >= total:
                break
        if listings:
            return listings
    return []


async def _from_web_search(client: AsyncTavilyClient, site: str, criteria: dict) -> list[Listing]:
    result = await client.search(
        query=criteria["search_query"],
        include_domains=[site],
        search_depth="advanced",
        max_results=get_settings().max_listings_per_site,
        include_raw_content="text",
    )
    pages = result.get("results", [])
    listings = [listing for page in pages for listing in extract_listings(site, page)]
    log.info("%s web search: %d pages -> %d product records", site, len(pages), len(listings))
    return listings


async def scrape_site(state: dict) -> dict:
    """Receives {"site": ..., "criteria": ...} via LangGraph Send."""
    site = domain_of(state["site"])
    criteria = state["criteria"]
    client = AsyncTavilyClient(api_key=get_settings().tavily_api_key)

    listings: list[Listing] = []
    try:
        if site in SEARCH_URLS:
            listings = await _from_site_search(client, site, criteria)
        if not listings:
            listings = await _from_web_search(client, site, criteria)
    except Exception:
        # One site failing should not stop the other sites.
        log.exception("scraping failed for %s", site)
    return {"raw_listings": listings}
