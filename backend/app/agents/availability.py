"""check_availability (plain Python): for vehicles sent in earlier reports that are missing from
today's results, open each ad's own page to see whether it's really gone.

A vehicle can drop out of the results without being sold (e.g. it moved past the pages we fetch),
so only a removed ad counts as unavailable.
"""
import logging

from tavily import AsyncTavilyClient

from app.agents.state import PipelineState
from app.config import get_settings

log = logging.getLogger(__name__)

# riyasewana shows "This ad is no longer available"; ikman's removed ads fail to load.
GONE_MARKERS = ("no longer available", "ad has been removed", "ad has expired", "ad not found", "ad is unavailable")
BATCH = 20  # Tavily extract accepts up to 20 URLs per call


async def check_availability(state: PipelineState) -> dict:
    still_available = list(state.get("still_listed", []))
    missing = state.get("missing", [])
    unavailable = []
    if not missing:
        return {"still_available": still_available, "unavailable": unavailable}

    client = AsyncTavilyClient(api_key=get_settings().tavily_api_key)
    for i in range(0, len(missing), BATCH):
        batch = missing[i:i + BATCH]
        try:
            result = await client.extract(urls=[m["url"] for m in batch], extract_depth="advanced")
        except Exception:
            # Couldn't check: leave these out of both lists so their status doesn't change today.
            log.exception("availability check failed for %d ads", len(batch))
            continue
        pages = {r["url"].rstrip("/"): r.get("raw_content") or "" for r in result.get("results", [])}
        failed = {f["url"].rstrip("/") for f in result.get("failed_results", [])}
        for m in batch:
            url = m["url"].rstrip("/")
            text = pages.get(url)
            if url in failed or (text is not None and any(marker in text.lower() for marker in GONE_MARKERS)):
                unavailable.append(m)
            elif text is not None:
                still_available.append(m)  # not in today's results, but the ad is still up
            else:
                log.warning("no availability result for %s", url)

    log.info("availability: %d still available, %d no longer available", len(still_available), len(unavailable))
    return {"still_available": still_available, "unavailable": unavailable}
