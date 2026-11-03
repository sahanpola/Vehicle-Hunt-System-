"""REST API with the pipeline replaced, so no scraping or LLM calls happen."""
import pytest
from fastapi.testclient import TestClient

from app import scheduler
from app.api import routes
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def body(**kw):
    return {"email": "buyer@example.com", "vehicle_query": "BMW 320d under 9M",
            "sites": ["https://ikman.lk"], "scrape_time": "08:30", **kw}


def test_create_schedules_and_delete_unschedules(client):
    r = client.post("/api/requests", json=body())
    assert r.status_code == 201
    rid = r.json()["id"]
    job = scheduler.scheduler.get_job(f"search-{rid}")
    assert job is not None and (job.trigger.fields[5].expressions[0].first, job.trigger.fields[6].expressions[0].first) == (8, 30)

    paused = client.patch(f"/api/requests/{rid}", json={"active": False}).json()
    assert paused["active"] is False and scheduler.scheduler.get_job(f"search-{rid}") is None

    assert client.delete(f"/api/requests/{rid}").status_code == 204
    assert client.get(f"/api/requests/{rid}/reports").status_code == 404


@pytest.mark.parametrize("bad", [
    {"email": "not-an-email"}, {"scrape_time": "25:00"}, {"sites": []}, {"vehicle_query": "x"},
])
def test_validation(client, bad):
    assert client.post("/api/requests", json=body(**bad)).status_code == 422


def test_run_now_starts_pipeline(client, monkeypatch):
    started = []

    async def fake_run(request_id):
        started.append(request_id)
    monkeypatch.setattr(routes, "run_search", fake_run)
    rid = client.post("/api/requests", json=body()).json()["id"]
    assert client.post(f"/api/requests/{rid}/run").status_code == 202
    assert started == [rid]


def test_sites_presets(client):
    assert client.get("/api/sites").json() == ["https://riyasewana.com/search", "https://ikman.lk"]
