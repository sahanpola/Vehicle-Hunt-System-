from urllib.parse import parse_qs, urlparse

from app.agents.sites import ikman, riyasewana


def criteria(**kw):
    return {"make": "Mitsubishi", "model": "Lancer", "year_min": 2005, "year_max": 2015, "max_price_lkr": 8_000_000,
            "vehicle_type": "car", "transmission": "automatic", "fuel": None, **kw}


def query(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_riyasewana_uses_search_form_fields():
    url, fallback = riyasewana(criteria())
    assert url.startswith("https://riyasewana.com/search.php?")
    q = query(url)
    assert q["make"] == "Mitsubishi" and q["model"] == "Lancer" and q["vtype"] == "cars"
    assert q["year"] == "2005" and q["year_max"] == "2015" and q["pricemmax"] == "8000000"
    assert q["trans"] == "Automatic" and q["fuel"] == "Any"
    assert "model" not in query(fallback)  # make-only fallback


def test_riyasewana_paging_and_vehicle_types():
    assert query(riyasewana(criteria(), page=2)[0])["page"] == "2"
    assert query(riyasewana(criteria(vehicle_type="three_wheeler"))[0])["vtype"] == "three-wheels"
    assert query(riyasewana(criteria(vehicle_type="motorcycle"))[0])["vtype"] == "motorcycles"
    assert query(riyasewana(criteria(make="Mercedes Benz"))[0])["make"] == "Mercedes-Benz"


def test_ikman_path_filters_and_fallback():
    url, fallback = ikman(criteria())
    assert urlparse(url).path == "/en/ads/sri-lanka/cars/mitsubishi/lancer"
    assert urlparse(fallback).path == "/en/ads/sri-lanka/cars/mitsubishi"
    q = query(url)
    assert q["money.price.maximum"] == "8000000"
    assert q["numeric.model_year.minimum"] == "2005" and q["numeric.model_year.maximum"] == "2015"
    assert q["enum.transmission"] == "automatic"
    assert "enum.fuel_type" not in q and "page" not in q


def test_ikman_categories_and_no_model():
    assert "/three-wheelers/bajaj/re" in ikman(criteria(make="Bajaj", model="RE", vehicle_type="three_wheeler"))[0]
    assert "/motorbikes-scooters/honda" in ikman(criteria(make="Honda", model=None, vehicle_type="motorcycle"))[0]
    assert len(ikman(criteria(model=None))) == 1
    assert query(ikman(criteria(), page=3)[0])["page"] == "3"
