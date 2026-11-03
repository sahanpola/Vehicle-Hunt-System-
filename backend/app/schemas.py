from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SearchRequestCreate(BaseModel):
    email: EmailStr
    vehicle_query: str = Field(min_length=2, examples=["BMW 320d 2012-2016 under 9 million"])
    sites: list[str] = Field(min_length=1)
    scrape_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["08:00"])


class SearchRequestUpdate(BaseModel):
    active: bool | None = None
    scrape_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class SearchRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    vehicle_query: str
    sites: list[str]
    scrape_time: str
    active: bool
    created_at: datetime


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    created_at: datetime
    status: str
    listings_found: int
    top_listings: list
    still_available: list
    unavailable: list
    summary: str
    error: str
