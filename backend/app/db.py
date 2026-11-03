from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import get_settings

def utcnow() -> datetime:
    """Current UTC time without tzinfo (how times are stored; the UI treats them as UTC)."""
    return datetime.now(UTC).replace(tzinfo=None)


engine = create_engine(get_settings().database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SearchRequest(Base):
    """One user's saved search. Runs every day at `scrape_time`."""

    __tablename__ = "search_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    vehicle_query: Mapped[str] = mapped_column(Text)
    sites: Mapped[list[str]] = mapped_column(JSON)
    scrape_time: Mapped[str] = mapped_column(String(5))  # "HH:MM"
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    reports: Mapped[list["Report"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="Report.created_at.desc()"
    )
    tracked: Mapped[list["TrackedListing"]] = relationship(cascade="all, delete-orphan")


class Report(Base):
    """Result of one pipeline run."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("search_requests.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | done | failed
    listings_found: Mapped[int] = mapped_column(Integer, default=0)
    top_listings: Mapped[list] = mapped_column(JSON, default=list)  # new today, ranked
    still_available: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")  # sent before, still listed
    unavailable: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")  # sent before, ad now gone
    summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")

    request: Mapped[SearchRequest] = relationship(back_populates="reports")


class TrackedListing(Base):
    """A vehicle already analysed for a search, so later runs can tell new, still-available and gone apart."""

    __tablename__ = "tracked_listings"
    __table_args__ = (UniqueConstraint("request_id", "key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("search_requests.id"), index=True)
    key: Mapped[str] = mapped_column(String(500))  # usually the ad URL
    url: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON)  # latest record incl. scores and rank reason
    sent: Mapped[bool] = mapped_column(Boolean, default=False)  # included in an email
    status: Mapped[str] = mapped_column(String(20), default="available")  # available | unavailable
    sent_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    unavailable_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


def _add_missing_columns() -> None:
    """create_all() doesn't alter existing tables, so add columns introduced after the DB was created."""
    insp = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing:
                continue
            default = f" DEFAULT '{col.server_default.arg}'" if col.server_default is not None else ""
            with engine.begin() as conn:
                conn.exec_driver_sql(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}{default}")


def init_db() -> None:
    Base.metadata.create_all(engine)
    _add_missing_columns()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
