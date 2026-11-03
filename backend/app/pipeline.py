"""Runs the agent graph for one saved search and stores the result as a Report."""
import logging

from app.agents.graph import graph
from app.db import Report, SearchRequest, SessionLocal
from app.history import load_known, save_run

log = logging.getLogger(__name__)


async def run_search(request_id: int) -> int | None:
    """Returns the new report id (None if the request no longer exists)."""
    with SessionLocal() as db:
        req = db.get(SearchRequest, request_id)
        if req is None:
            return None
        report = Report(request_id=req.id, status="running")
        db.add(report)
        db.commit()
        initial = {"request_id": req.id, "email": req.email, "vehicle_query": req.vehicle_query, "sites": req.sites,
                   "known": load_known(req.id)}

    log.info("running search %s: %s", request_id, initial["vehicle_query"])
    try:
        result = await graph.ainvoke(initial)
        save_run(request_id, result)
        update = {
            "status": "done",
            "listings_found": result.get("found_count", 0),
            "top_listings": result.get("top_listings", []),
            "still_available": result.get("still_available", []),
            "unavailable": result.get("unavailable", []),
            "summary": result.get("summary", ""),
            "error": result.get("email_error", ""),
        }
    except Exception as e:
        log.exception("search %s failed", request_id)
        update = {"status": "failed", "error": str(e)}

    with SessionLocal() as db:
        report = db.get(Report, report.id)
        for k, v in update.items():
            setattr(report, k, v)
        db.commit()
    return report.id
