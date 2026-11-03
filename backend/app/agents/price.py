"""price agent (LLM): compare each asking price with the rest of the market."""
import json

from pydantic import BaseModel, Field

from app.agents.llm import ask
from app.agents.state import PipelineState, listings_for_prompt


class ListingPrice(BaseModel):
    listing_id: str
    price_comment: str = Field(description="One line: below / around / above market and why")


class PriceAnalysis(BaseModel):
    listings: list[ListingPrice]
    market_summary: str = Field(description="2-3 sentences on the price range seen")


SYSTEM = (
    "You are a used-car price analyst for the Sri Lankan market. Compare each listing's price_lkr "
    "with the other listings of similar model, year and mileage. A listing without price_lkr is "
    "'Negotiable'; say so rather than guessing a price."
)


async def price(state: PipelineState) -> dict:
    listings = state.get("listings", [])
    if not listings:
        return {"price": {}}

    fields = ("id", "title", "price_lkr", "year", "mileage_km", "details")  # no descriptions needed here
    prompt = (
        f"Buyer criteria: {json.dumps(state['criteria'])}\n\n"
        f"Listings:\n{listings_for_prompt(listings, fields)}"
    )
    result = await ask(SYSTEM, prompt, PriceAnalysis)
    by_id = {p.listing_id: p.model_dump(exclude={"listing_id"}) for p in result.listings}
    by_id["_market"] = result.market_summary
    return {"price": by_id}
