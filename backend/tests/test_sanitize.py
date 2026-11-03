from app.agents.sanitize import dedupe_key, extract_listings, filter_by_criteria, parse_results_page
from tests.conftest import ikman_card, listing, riya_card


def test_ikman_cards_for_different_vehicle_types():
    md = "40 ads\n" + "".join([
        ikman_card("bmw-1", "BMW 320d 2013", 57_840, 16_395_000),
        ikman_card("dio-1", "Honda Dio 2017", 23_500, 65_000, attrs="Used", category="Scooters"),
        ikman_card("hiace-1", "Toyota Hiace GDH 2025", 22_000, 23_200_000, attrs="Used | 2,800 cc", category="Vans"),
        ikman_card("re-1", "Bajaj RE 2014", 18_000, 195_000, attrs="Brand New", category="Three Wheelers"),
    ])
    cards, total = parse_results_page("ikman.lk", md)
    assert total == 40
    assert [c["title"] for c in cards] == ["BMW 320d 2013", "Honda Dio 2017", "Toyota Hiace GDH 2025", "Bajaj RE 2014"]
    bmw, dio, van, re3 = cards
    assert (bmw["price_lkr"], bmw["year"], bmw["mileage_km"], bmw["details"]) == (16_395_000, 2013, 57_840, "Saloon, Used")
    assert bmw["url"] == "https://ikman.lk/en/ad/bmw-1" and bmw["source"] == "card"
    assert dio["details"] == "Used" and van["details"] == "Used, 2,800 cc" and re3["details"] == "Brand New"


def test_riyasewana_cards_including_dealer_and_negotiable():
    md = "Displaying 1 - 40 of 61 Search Results\n" + "".join([
        riya_card("lancer-1", "Mitsubishi Lancer CS1", "Rs. 6,800,000", 2013, "Kurunegala", 195_000),
        riya_card("lancer-2", "Mitsubishi Lancer EX", "Negotiable", 2010, "Piliyandala"),
        riya_card("lancer-3", "Mitsubishi Lancer Cs1", "Rs. 6,350,000", 2007, "Kottawa", 175_000, extra="Visit Showroom "),
        riya_card("re-1", "Bajaj 4 Stroke", "Rs. 1,385,000", 2013, "Malabe", 91_000, vtype="Three Wheel"),
    ])
    cards, total = parse_results_page("riyasewana.com", md)
    assert total == 61 and len(cards) == 4
    assert cards[0]["title"] == "Mitsubishi Lancer CS1 2013"
    assert (cards[0]["price_lkr"], cards[0]["mileage_km"], cards[0]["location"]) == (6_800_000, 195_000, "Kurunegala")
    assert cards[1]["price_lkr"] is None and cards[1]["location"] == "Piliyandala"
    assert cards[2]["location"] == "Kottawa" and cards[2]["mileage_km"] == 175_000  # dealer card
    assert cards[3]["title"] == "Bajaj 4 Stroke 2013"  # " Three Wheel" suffix removed
    assert cards[0]["url"] == "https://riyasewana.com/buy/lancer-1"


def test_placeholder_mileage_is_unknown():
    md = ikman_card("x", "BMW 320d 2008", 1_000, 9_000_000) + ikman_card("y", "BMW 320d 2009", 199, 9_100_000)
    cards, _ = parse_results_page("ikman.lk", md)
    assert [c["mileage_km"] for c in cards] == [None, None]


def test_ikman_spare_part_ad_is_dropped():
    page = {"url": "https://ikman.lk/en/ad/bmw-320d-engine", "title": "BMW 320D Engine | ikman",
            "raw_content": "BMW 320D Engine\nRs 1,380,000\nCondition:\nUsed\nPart or Accessory Type:\nEngines\nBrand:\nBMW"}
    assert extract_listings("ikman.lk", page) == []


def test_filter_by_criteria():
    items = [
        listing(url="1", title="BMW 320d 2013", year=2013, price=16_000_000),
        listing(url="2", title="Toyota Axio 2014", year=2014, price=9_500_000),  # wrong make
        listing(url="3", title="BMW 320d 2008", year=2008, price=7_000_000),  # too old
        listing(url="4", title="BMW 320d 2015", year=2015, price=25_000_000),  # over budget
        listing(url="5", title="BMW 520d 2014", year=2014, price=15_000_000),  # other model
        listing(url="6", title="BMW 320d 2014", year=2014, price=None),  # negotiable: kept
    ]
    kept = filter_by_criteria(items, {"make": "BMW", "model": "320d", "year_min": 2010, "max_price_lkr": 20_000_000})
    assert [l["url"] for l in kept] == ["1", "6"]


def test_model_filter_skipped_when_no_title_uses_it():
    items = [listing(url="1", title="BMW 318i 2016"), listing(url="2", title="BMW 320d 2014")]
    assert len(filter_by_criteria(items, {"make": "BMW", "model": "3 Series"})) == 2


def test_dedupe_key_matches_same_vehicle_from_ad_and_card():
    ad = listing(url="https://ikman.lk/en/ad/a", source="ad")
    card = listing(url="https://ikman.lk/en/ads/sri-lanka/cars/bmw", source="search_page")
    assert dedupe_key(ad) == dedupe_key(card)
