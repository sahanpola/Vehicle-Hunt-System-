"""Daily schedule: one cron job per active search, at its scrape_time."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.db import SearchRequest, SessionLocal
from app.pipeline import run_search

scheduler = AsyncIOScheduler(timezone=get_settings().timezone)


def _job_id(request_id: int) -> str:
    return f"search-{request_id}"


def schedule(req: SearchRequest) -> None:
    if not req.active:
        unschedule(req.id)
        return
    hour, minute = req.scrape_time.split(":")
    scheduler.add_job(
        run_search,
        CronTrigger(hour=int(hour), minute=int(minute)),
        args=[req.id],
        id=_job_id(req.id),
        replace_existing=True,
        misfire_grace_time=3600,
    )


def unschedule(request_id: int) -> None:
    if scheduler.get_job(_job_id(request_id)):
        scheduler.remove_job(_job_id(request_id))


def start() -> None:
    with SessionLocal() as db:
        for req in db.query(SearchRequest).filter_by(active=True):
            schedule(req)
    scheduler.start()
