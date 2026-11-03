from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app import scheduler
from app.db import Report, SearchRequest, get_db
from app.pipeline import run_search
from app.schemas import ReportOut, SearchRequestCreate, SearchRequestOut, SearchRequestUpdate

router = APIRouter(prefix="/api")

# Sites shown as presets in the UI. Only the domain is used: the search URL is built
# from each request's criteria (see agents/sites.py).
DEFAULT_SITES = [
    "https://riyasewana.com/search",
    "https://ikman.lk",
]


def _get_request(db: Session, request_id: int) -> SearchRequest:
    req = db.get(SearchRequest, request_id)
    if req is None:
        raise HTTPException(404, "Search request not found")
    return req


@router.get("/sites")
def list_sites() -> list[str]:
    return DEFAULT_SITES


@router.post("/requests", response_model=SearchRequestOut, status_code=201)
def create_request(body: SearchRequestCreate, db: Session = Depends(get_db)):
    req = SearchRequest(**body.model_dump())
    db.add(req)
    db.commit()
    scheduler.schedule(req)
    return req


@router.get("/requests", response_model=list[SearchRequestOut])
def list_requests(email: str | None = None, db: Session = Depends(get_db)):
    q = db.query(SearchRequest).order_by(SearchRequest.created_at.desc())
    if email:
        q = q.filter(SearchRequest.email == email)
    return q.all()


@router.patch("/requests/{request_id}", response_model=SearchRequestOut)
def update_request(request_id: int, body: SearchRequestUpdate, db: Session = Depends(get_db)):
    req = _get_request(db, request_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(req, k, v)
    db.commit()
    scheduler.schedule(req)
    return req


@router.delete("/requests/{request_id}", status_code=204)
def delete_request(request_id: int, db: Session = Depends(get_db)):
    req = _get_request(db, request_id)
    scheduler.unschedule(req.id)
    db.delete(req)
    db.commit()


@router.post("/requests/{request_id}/run", status_code=202)
def run_now(request_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger the pipeline immediately instead of waiting for the daily run."""
    _get_request(db, request_id)
    background.add_task(run_search, request_id)
    return {"status": "started"}


@router.get("/requests/{request_id}/reports", response_model=list[ReportOut])
def list_reports(request_id: int, db: Session = Depends(get_db)):
    _get_request(db, request_id)
    return db.query(Report).filter_by(request_id=request_id).order_by(Report.created_at.desc()).limit(30).all()
