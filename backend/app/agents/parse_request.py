"""parse_request agent (LLM, structured output): free text -> search criteria."""
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.llm import ask
from app.agents.state import PipelineState


class SearchCriteria(BaseModel):
    make: str
    model: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    max_price_lkr: int | None = Field(default=None, description="Budget in Sri Lankan rupees")
    vehicle_type: Literal["car", "suv", "van", "pickup", "crew_cab", "motorcycle", "three_wheeler",
                          "bus", "lorry", "heavy_duty", "tractor", "bicycle"] = "car"
    transmission: Literal["automatic", "manual"] | None = None
    fuel: Literal["petrol", "diesel", "hybrid", "electric"] | None = None
    search_query: str = Field(description="Short web search query for car-for-sale ads, e.g. 'BMW 320d for sale'")
    notes: str = Field(default="", description="Other preferences, e.g. colour, trim")


SYSTEM = (
    "You turn a buyer's description of the vehicle they want into search criteria for "
    "Sri Lankan used-car sites. Amounts like '9M', '90 lakhs' or '9 million' are LKR. "
    "Fill in make and model as the sites list them (e.g. make 'Mercedes-Benz', model 'C200'; "
    "make 'Bajaj', model 'RE' for a three-wheeler; make 'Honda', model 'Dio' for a scooter). "
    "Leave a field null when the buyer didn't specify it."
)


async def parse_request(state: PipelineState) -> dict:
    criteria = await ask(SYSTEM, state["vehicle_query"], SearchCriteria, effort="low")
    return {"criteria": criteria.model_dump()}
