"""Per-search memory of vehicles already analysed and sent (tracked_listings table).

load_known() feeds the graph before a run; save_run() records the outcome after it.
"""
from app.agents.state import listing_key
from app.db import SessionLocal, TrackedListing, utcnow


def load_known(request_id: int) -> dict[str, dict]:
    with SessionLocal() as db:
        rows = db.query(TrackedListing).filter_by(request_id=request_id).all()
        return {
            r.key: {
                "url": r.url, "data": r.data, "sent": r.sent, "status": r.status,
                "sent_price": r.sent_price, "last_price": r.last_price,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            }
            for r in rows
        }


def save_run(request_id: int, result: dict) -> None:
    now = utcnow()
    top = {listing_key(t): t for t in result.get("top_listings", [])}

    with SessionLocal() as db:
        rows = {r.key: r for r in db.query(TrackedListing).filter_by(request_id=request_id)}

        # Every vehicle analysed today is remembered, so it isn't analysed (and paid for) again.
        # Only the ones in today's top list count as sent.
        for listing in result.get("listings", []):
            key = listing_key(listing)
            row = rows.get(key) or TrackedListing(request_id=request_id, key=key, url=listing["url"], first_seen_at=now)
            row.data = {k: v for k, v in top.get(key, listing).items() if k != "id"}
            row.last_price, row.last_seen_at = listing.get("price_lkr"), now
            if key in top:
                row.sent, row.sent_at, row.sent_price, row.status = True, now, listing.get("price_lkr"), "available"
            db.add(row)

        for view in result.get("still_available", []):
            if row := rows.get(view["key"]):
                row.status, row.unavailable_at, row.last_seen_at = "available", None, now
                row.last_price = view.get("price_lkr") or row.last_price

        for view in result.get("unavailable", []):
            if row := rows.get(view["key"]):
                row.status, row.unavailable_at = "unavailable", now

        db.commit()
