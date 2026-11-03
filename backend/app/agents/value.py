"""value agent (LLM): how well does each listing match the buyer and what do they get for the money."""
import json

from pydantic import BaseModel, Field

from app.agents.llm import ask
from app.agents.state import PipelineState, listings_for_prompt


class ListingValue(BaseModel):
    listing_id: str
    value_score: int = Field(ge=1, le=10, description="10 = great match and great value for money")
    reasoning: str = Field(description="One sentence")


class ValueAnalysis(BaseModel):
    listings: list[ListingValue]


SYSTEM = (
    "You advise a car buyer in Sri Lanka. Score each listing on value: how closely it matches "
    "the buyer's criteria (make, model, years, budget, preferences) and what they get for the money "
    "(spec, trim, year, mileage, resale value of the model). Listings that are not a single car ad "
    "or do not match the requested vehicle score 1."
)


async def value(state: PipelineState) -> dict:
    listings = state.get("listings", [])
    if not listings:
        return {"value": {}}

    prompt = (
        f"Buyer request: {state['vehicle_query']}\n"
        f"Parsed criteria: {json.dumps(state['criteria'])}\n\n"
        f"Listings:\n{listings_for_prompt(listings)}"
    )
    result = await ask(SYSTEM, prompt, ValueAnalysis)
    return {"value": {v.listing_id: v.model_dump(exclude={"listing_id"}) for v in result.listings}}
