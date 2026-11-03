"""Turns raw scraped pages into compact product records (plain Python, no LLM).

Tavily returns whole pages: menus, image captions, footers, "related ads", spare parts.
Here we keep only vehicles for sale and only the fields the agents need, so the LLM
prompts stay small.

Inputs:
  - parse_results_page(): a site's own search-results page fetched as markdown
    (built by sites.py). Each card has its own ad link. This is the main path.
  - extract_listings(): Tavily web-search results (fallback, and for sites without
    a URL builder). Ad pages and search pages as plain text; unknown sites use a
    generic cleaner.
"""
import re

from app.agents.state import Listing

DESCRIPTION_CHARS = 500
GENERIC_CHARS = 800

YEAR = r"(?:19[5-9]\d|20[0-4]\d)"
AGO = r"(?:\d+\s?(?:m|h|d|mins?|hours?|days?) ago|Yesterday|Today|Just now|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}\b)"


# ---------- helpers ----------

def _flat(text: str) -> str:
    """Single-line text without image captions."""
    text = re.sub(r"Image \d+:?", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _int(s: str | None) -> int | None:
    """First number in the text: 'Rs. 6,090,000 Negotiable' -> 6090000"""
    m = re.search(r"\d[\d,]*", s or "")
    return int(m.group().replace(",", "")) if m else None


def _fields(keys: list[str], text: str, sep: str = "") -> dict[str, str]:
    """'Year: 2014 Fuel: Diesel' -> {'Year': '2014', 'Fuel': 'Diesel'}.
    First occurrence wins, so the same words inside the seller's description don't override the spec table.
    """
    alt = "|".join(keys)
    found: dict[str, str] = {}
    for k, v in re.findall(rf"\b({alt}){sep}\s*(.+?)(?=\s+(?:{alt}){sep}|$)", text):
        found.setdefault(k, v.strip())
    return found


def _year_in(text: str) -> int | None:
    m = re.findall(rf"\b({YEAR})\b", text or "")
    return int(m[-1]) if m else None


def _between(text: str, start: str, end: str) -> str:
    m = re.search(rf"{start}\s*(.*?)\s*(?:{end}|$)", text)
    return m.group(1)[:DESCRIPTION_CHARS] if m else ""


MIN_REAL_MILEAGE = 1000  # sellers often type 1, 199 or 1000 km when they don't want to say


def _listing(site: str, url: str, title: str, source: str, **fields) -> Listing:
    if (fields.get("mileage_km") or 0) <= MIN_REAL_MILEAGE:
        fields["mileage_km"] = None
    return {"id": "", "site": site, "url": url, "title": title.strip(), "source": source, **fields}


# ---------- ikman.lk ----------

IKMAN_KEYS = ["Brand", "Model", "Trim / Edition", "Year", "Condition", "Transmission", "Body",
              "Fuel", "Engine", "Mileage", "Part or Accessory Type", "Description"]
IKMAN_CARD = re.compile(
    r"## (?P<title>[^#|]+?) (?P<km>[\d,]+) km \| (?P<body>[^|]+?) \| "
    r"(?P<cond>Used|Reconditioned|Brand New|New)(?: MEMBER)?(?: FEATURED)? (?P<loc>[^,#|]+?), Cars Rs (?P<price>[\d,]+)"
)


def _ikman_ad(site: str, r: dict) -> list[Listing]:
    text = _flat(r.get("raw_content") or r.get("content"))
    fields = _fields([re.escape(k) for k in IKMAN_KEYS], text, sep=":")
    if "Part or Accessory Type" in fields:  # spare part, not a vehicle
        return []
    price = re.search(r"Rs ([\d,]{4,})", text)
    loc = re.search(r"Posted on\s*[^,]+,\s*(.+?)\s+\d+\s*views", text)
    title = re.sub(r"\s+for Sale in .*$|\s*\|\s*ikman$", "", r.get("title", ""))
    details = ", ".join(fields[k][:40] for k in ("Trim / Edition", "Transmission", "Fuel", "Engine", "Body", "Condition") if k in fields)
    return [_listing(
        site, r["url"], title, "ad",
        price_lkr=_int(price.group(1)) if price else None,
        year=_int(fields.get("Year")) or _year_in(title),
        mileage_km=_int(fields.get("Mileage")),
        location=loc.group(1) if loc else "",
        details=details,
        description=_between(text, "Description", "Show more|For sale by|Stay Alert|MEMBER"),
    )]


def _ikman_search(site: str, r: dict) -> list[Listing]:
    text = _flat(r.get("raw_content"))
    return [
        _listing(
            site, r["url"], m["title"], "search_page",
            price_lkr=_int(m["price"]),
            year=_year_in(m["title"]),
            mileage_km=_int(m["km"]),
            location=m["loc"].strip(),
            details=f"{m['body'].strip()}, {m['cond']}",
            description="",
        )
        for m in IKMAN_CARD.finditer(text)
    ]


# ---------- riyasewana.com ----------

RIYA_KEYS = ["Location", "Year", "Mileage", "Make", "Model", "Gear", "Fuel Type", r"Engine \(cc\)",
             "Condition", "Ad Date", "Options", "More Details"]
RIYA_CARD = re.compile(
    rf"(?P<name>[A-Z][\w\-./]*(?: [\w\-./]+){{0,8}}?) (?P<y>{YEAR}) (?P<vt>[A-Z][a-zA-Z ]{{1,15}}?) (?P=name) (?P=vt) "
    rf"(?P<price>Rs\. [\d,]+|Negotiable) (?:{YEAR} )?(?P<loc>[A-Za-z][A-Za-z .\-]{{0,30}}?)(?:·(?P<km>[\d,]+) km)? {AGO}"
)


def _riya_ad(site: str, r: dict) -> list[Listing]:
    raw = r.get("raw_content")
    text = _flat(raw or r.get("content"))
    fields = _fields(RIYA_KEYS, text)
    price = re.search(r"Price\s+(Rs\. [\d,]+|Negotiable)", text) or re.search(r"Rs\.? ?([\d,]{5,})", r.get("title", ""))
    head = re.search(r"Back to results\)?\s*(.+?\((?:Used|New|Reconditioned)\))", text)
    title = head.group(1) if head else r.get("title", "")
    details = ", ".join(fields[k][:40] for k in ("Gear", "Fuel Type", r"Engine \(cc\)", "Condition") if k in fields)
    description = _between(text, "More Details", r"\d+ views|Report Ad") if raw else text[:DESCRIPTION_CHARS]
    return [_listing(
        site, r["url"], title, "ad",
        price_lkr=_int(price.group(1)) if price else None,
        year=_int(fields.get("Year")) or _year_in(text),
        mileage_km=_int(fields.get("Mileage") or (re.search(r"Mileage:?\s*([\d,]+)\s*km", text) or [""])[0]),
        location=fields.get("Location", "")[:40],
        details=details,
        description=description,
    )]


def _riya_search(site: str, r: dict) -> list[Listing]:
    text = _flat(r.get("raw_content"))
    return [
        _listing(
            site, r["url"], f"{m['name']} {m['y']}", "search_page",
            price_lkr=_int(m["price"]),
            year=int(m["y"]),
            mileage_km=_int(m["km"]),
            location=m["loc"].strip(),
            details=m["vt"].strip(),
            description="",
        )
        for m in RIYA_CARD.finditer(text)
    ]


# ---------- other sites ----------

def _generic(site: str, r: dict) -> list[Listing]:
    lines = (r.get("raw_content") or r.get("content") or "").splitlines()
    # drop menu items, image captions and other short fragments
    text = " ".join(l.strip() for l in lines if len(l.strip()) > 25 and not l.strip().startswith("Image"))
    price = re.search(r"(?:Rs\.?|LKR)\s?([\d,]{5,})", text)
    km = re.search(r"([\d,]{3,})\s?km\b", text)
    return [_listing(
        site, r["url"], r.get("title", ""), "page",
        price_lkr=_int(price.group(1)) if price else None,
        year=_year_in(r.get("title", "")),
        mileage_km=_int(km.group(1)) if km else None,
        location="",
        details="",
        description=text[:GENERIC_CHARS],
    )]


# ---------- search-results pages as markdown (Tavily extract) ----------

AD_LINK = {
    "ikman.lk": re.compile(r"https://ikman\.lk/en/ad/[\w\-]+"),
    "riyasewana.com": re.compile(r"https://riyasewana\.com/buy/[\w\-]+"),
}
# Attributes differ by vehicle type, but always end with the condition (and engine size for vans):
#   "BMW 320d 2013 57,840 km | Saloon | Used Colombo, Cars Rs 16,395,000"
#   "Honda Dio 2017 23,500 km | Used Colombo, Scooters Rs 65,000"
#   "Toyota Hiace 2025 22,000 km | Used | 2,800 cc Colombo, Vans Rs 23,200,000"
IKMAN_MD_CARD = re.compile(
    r"(?P<title>.+?) (?:(?P<km>[\d,]+) km )?\| (?P<attrs>[^,]*?(?:Used|Reconditioned|Brand New|New)(?: \| [\d,]+ cc)?) "
    r"(?P<loc>[^,|]+?), [A-Za-z &]+ Rs (?P<price>[\d,]+)"
)
RIYA_MD_CARD = re.compile(
    # city names are single tokens ("Dehiwala-Mount-Lavinia"); dealer cards add "Visit Showroom" after the mileage
    rf"(?P<price>Rs\. [\d,]+|Negotiable)(?: {YEAR})? (?P<loc>[A-Za-z][A-Za-z.\-]*)(?:·(?P<km>[\d,]+) km)?"
)
VEHICLE_WORD = re.compile(r"\s+(?:Car|SUV|Jeep|Van|Pickup|Double Cab|Crew Cab|Motorcycle|Motorbike|Scooter|Three Wheel|"
                          r"Lorry|Bus|Tractor|Heavy-Duty|Bicycle|Other)$")


def _card_text(chunk: str) -> str:
    """Markdown card -> plain text (no images, link targets or markup)."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", chunk)
    text = re.sub(r"\]\([^)]*\)", " ", text)
    text = re.sub(r"[\[\]*#]|\bFEATURED\b|\bMEMBER\b|\+\d+\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _ikman_card(site: str, url: str, text: str) -> Listing | None:
    m = IKMAN_MD_CARD.search(text)
    if not m:
        return None
    return _listing(
        site, url, m["title"], "card",
        price_lkr=_int(m["price"]), year=_year_in(m["title"]), mileage_km=_int(m["km"]),
        location=m["loc"].strip(), details=m["attrs"].replace(" | ", ", "), description="",
    )


def _riya_card(site: str, url: str, text: str, chunk: str) -> Listing | None:
    title = re.search(r'"([^"]+)"\)', chunk)  # link tooltip: "Mitsubishi Lancer CS1 2013 Car"
    m = RIYA_MD_CARD.search(text)
    if not (title and m):
        return None
    name = VEHICLE_WORD.sub("", title.group(1))
    return _listing(
        site, url, name, "card",
        price_lkr=_int(m["price"]), year=_year_in(name), mileage_km=_int(m["km"]),
        location=m["loc"].strip(), details="", description="",
    )


def parse_results_page(site: str, markdown: str) -> tuple[list[Listing], int | None]:
    """Cards on one results page, and the site's total result count (for paging)."""
    listings = []
    for chunk in re.split(r"\n\s*\*\s+(?=\[)", markdown):
        link = AD_LINK[site].search(chunk)
        if not link:
            continue
        text = _card_text(chunk)
        card = _ikman_card(site, link.group(), text) if site == "ikman.lk" else _riya_card(site, link.group(), text, chunk)
        if card:
            listings.append(card)

    total = re.search(r"of (\d[\d,]*) Search Results", markdown) or re.search(r"(\d[\d,]*) ads\b", markdown)
    return listings, _int(total.group(1)) if total else None


# ---------- entry points ----------

def extract_listings(site: str, result: dict) -> list[Listing]:
    """One Tavily result -> zero or more product records."""
    url = result["url"]
    if site == "ikman.lk":
        if "/en/ad/" in url:
            return _ikman_ad(site, result)
        return _ikman_search(site, result) if "/ads/" in url else []
    if site == "riyasewana.com":
        if "/buy/" in url:
            return _riya_ad(site, result)
        return _riya_search(site, result) if "/search/" in url else []
    return _generic(site, result)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def filter_by_criteria(listings: list[Listing], criteria: dict) -> list[Listing]:
    """Drop listings that clearly don't match the buyer (wrong make, year or over budget)."""
    make = _norm(criteria.get("make"))
    y_min, y_max, budget = criteria.get("year_min"), criteria.get("year_max"), criteria.get("max_price_lkr")

    def ok(l: Listing) -> bool:
        if make and make not in _norm(l["title"] + l["description"][:200]):
            return False
        if l["year"] and ((y_min and l["year"] < y_min) or (y_max and l["year"] > y_max)):
            return False
        if l["price_lkr"] and budget and l["price_lkr"] > budget:
            return False
        return True

    kept = [l for l in listings if ok(l)]

    # Model names vary ("3 Series" vs "320d"), so only filter on model when some titles use it.
    model = _norm(criteria.get("model"))
    if model:
        by_model = [l for l in kept if model in _norm(l["title"])]
        if by_model:
            kept = by_model
    return kept


def dedupe_key(l: Listing) -> tuple:
    """Same car often appears as an ad page and as a card on a search page."""
    if l["price_lkr"] and l["mileage_km"]:
        return (l["site"], l["price_lkr"], l["mileage_km"], l["year"])
    if l["source"] == "ad":
        return (l["url"],)
    return (l["site"], _norm(l["title"]), l["price_lkr"], _norm(l["location"]))
