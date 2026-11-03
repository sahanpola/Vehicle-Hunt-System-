"""collect (plain Python): merge all sites, drop non-matching vehicles, dedupe, and split them into
new vehicles (to analyse) and vehicles already sent in earlier reports."""
import logging

from app.agents.sanitize import dedupe_key, filter_by_criteria
from app.agents.state import PipelineState, listing_key
from app.config import get_settings

log = logging.getLogger(__name__)


def sent_view(key: str, info: dict, current: dict | None = None) -> dict:
    """A previously sent vehicle, with today's price/mileage when it is in today's results."""
    view = {**info["data"], "key": key, "url": info["url"], "sent_price": info["sent_price"], "sent_at": info["sent_at"]}
    if current:
        view.update({k: current[k] for k in ("price_lkr", "mileage_km", "location") if current.get(k)})
    else:
        view["price_lkr"] = info["last_price"]
    if view.get("price_lkr") and view["sent_price"]:
        view["price_change"] = view["price_lkr"] - view["sent_price"]
    return view


async def collect(state: PipelineState) -> dict:
    raw = state.get("raw_listings", [])
    matching = filter_by_criteria(raw, state["criteria"])

    # Ad pages first (full details, so they win over the same vehicle's card), then alternate
    # between sites so the cap below doesn't fill up from the first site only.
    position: dict[str, int] = {}
    order = {}
    for l in matching:
        position[l["site"]] = position.get(l["site"], 0) + 1
        order[id(l)] = (l["source"] != "ad", position[l["site"]])
    matching.sort(key=lambda l: order[id(l)])

    seen: set[tuple] = set()
    found = []
    for item in matching:
        key = dedupe_key(item)
        if key not in seen:
            seen.add(key)
            found.append(item)

    # Split against what earlier runs stored for this search.
    known = state.get("known", {})
    new, still_listed, present = [], [], set()
    for item in found:
        key = listing_key(item)
        info = known.get(key)
        if info is None:
            new.append(item)
        elif info["sent"]:
            present.add(key)
            still_listed.append(sent_view(key, info, current=item))
        # analysed before but not sent (didn't make the top 10): skip, it was already judged
    missing = [sent_view(k, info) for k, info in known.items()
               if info["sent"] and info["status"] == "available" and k not in present]

    limit = get_settings().max_listings_to_analyse
    listings = [{**item, "id": f"L{i}"} for i, item in enumerate(new[:limit], start=1)]
    log.info("collect: %d records -> %d matching -> %d unique: %d new (analysing %d), %d sent before still listed, %d missing",
             len(raw), len(matching), len(found), len(new), len(listings), len(still_listed), len(missing))
    return {"listings": listings, "found_count": len(found), "still_listed": still_listed, "missing": missing}
