"""Builds each site's own search-results URL from the buyer's criteria.

The site applies the filters itself (make, model, year, price, gear, fuel), so we fetch
one or two result pages instead of guessing with a web search.
To support a new site: add a function here and register it in SEARCH_URLS.
"""
import re
from urllib.parse import urlencode

# vehicle_type (from parse_request) -> each site's category
RIYASEWANA_VTYPE = {
    "car": "cars", "suv": "suvs", "van": "vans", "pickup": "pickups", "crew_cab": "crew-cabs",
    "motorcycle": "motorcycles", "three_wheeler": "three-wheels", "bus": "buses", "lorry": "lorries",
    "heavy_duty": "heavy-duties", "tractor": "tractors", "bicycle": "bicycles",
}
IKMAN_CATEGORY = {
    "car": "cars", "suv": "cars", "pickup": "cars", "crew_cab": "cars",  # ikman lists these under Cars
    "van": "vans", "motorcycle": "motorbikes-scooters", "three_wheeler": "three-wheelers", "bus": "buses",
    "lorry": "lorries", "heavy_duty": "heavy-duty", "tractor": "tractors", "bicycle": "bicycles",
}


def _slug(s: str | None) -> str:
    """'Mercedes Benz' -> 'mercedes-benz'"""
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def riyasewana(c: dict, page: int = 1) -> list[str]:
    """https://riyasewana.com/search.php?make=BMW&model=320d&vtype=cars&year=2012&year_max=2016&pricemmax=9000000

    Returns the make+model URL and a make-only fallback (in case the model text matches nothing).
    """
    params = {
        "make": (c.get("make") or "Any").strip().replace(" ", "-"),
        "model": c.get("model") or "",
        "vtype": RIYASEWANA_VTYPE.get(c.get("vehicle_type") or "car", "cars"),
        "year": c.get("year_min") or "",
        "year_max": c.get("year_max") or "",
        "pricemmax": c.get("max_price_lkr") or "",
        "trans": (c.get("transmission") or "Any").capitalize(),
        "fuel": c.get("fuel") or "Any",
        "srch_btn": 1,
    }
    if page > 1:
        params["page"] = page
    urls = [f"https://riyasewana.com/search.php?{urlencode(params)}"]
    if params["model"]:
        urls.append(f"https://riyasewana.com/search.php?{urlencode({**params, 'model': ''})}")
    return urls


def ikman(c: dict, page: int = 1) -> list[str]:
    """https://ikman.lk/en/ads/sri-lanka/cars/bmw/320d?money.price.maximum=...&numeric.model_year.minimum=...

    Returns the brand+model URL and a brand-only fallback (ikman's model slugs don't
    always match how buyers write the model, and an unknown slug fails to load).
    """
    params = {
        "money.price.maximum": c.get("max_price_lkr"),
        "numeric.model_year.minimum": c.get("year_min"),
        "numeric.model_year.maximum": c.get("year_max"),
        "enum.transmission": (c.get("transmission") or "").lower() or None,
        "enum.fuel_type": (c.get("fuel") or "").lower() or None,
        "page": page if page > 1 else None,
    }
    query = urlencode({k: v for k, v in params.items() if v})
    base = f"https://ikman.lk/en/ads/sri-lanka/{IKMAN_CATEGORY.get(c.get('vehicle_type') or 'car', 'cars')}"
    brand, model = _slug(c.get("make")), _slug(c.get("model"))
    candidates = [f"{base}/{brand}/{model}", f"{base}/{brand}"] if model else [f"{base}/{brand}"]
    return [f"{u}?{query}" if query else u for u in candidates]


# domain -> builder(criteria, page) -> candidate URLs, best first
SEARCH_URLS = {
    "riyasewana.com": riyasewana,
    "ikman.lk": ikman,
}
