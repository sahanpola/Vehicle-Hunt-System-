"""rank agent (LLM): combine price, condition and value into a top-10 list."""
import json

from pydantic import BaseModel, Field

from app.agents.llm import ask
from app.agents.state import PipelineState, compact

TOP_N = 10
# What the ranker sees: scores and comments, not the seller's full description.
RANK_FIELDS = ("id", "title", "price_lkr", "year", "mileage_km", "details", "price_comment",
               "condition_score", "red_flags", "value_score")


class RankedItem(BaseModel):
    listing_id: str
    reason: str = Field(description="One sentence on why it is ranked here")


class Ranking(BaseModel):
    ranked: list[RankedItem] = Field(description=f"Best first, at most {TOP_N}")


SYSTEM = (
    f"You pick the best {TOP_N} cars for a buyer. Weigh the price analysis, condition assessment "
    "and value score together. Leave out results that are not real ads for the requested vehicle. "
    "Return fewer than the maximum if fewer are worth recommending."
)


async def rank(state: PipelineState) -> dict:
    listings = state.get("listings", [])
    if not listings:
        return {"top_listings": []}

    price, condition, value = state.get("price", {}), state.get("condition", {}), state.get("value", {})
    merged = [
        {
            **l,
            **price.get(l["id"], {}),
            **condition.get(l["id"], {}),
            **value.get(l["id"], {}),
        }
        for l in listings
    ]

    prompt = (
        f"Buyer request: {state['vehicle_query']}\n"
        f"Market: {price.get('_market', '')}\n\n"
        f"Analysed listings:\n{chr(10).join(json.dumps(compact(m, RANK_FIELDS), ensure_ascii=False) for m in merged)}"
    )
    result = await ask(SYSTEM, prompt, Ranking)

    by_id = {m["id"]: m for m in merged}
    valid, picked = [], set()
    for r in result.ranked:  # skip unknown ids and repeats of the same car
        if r.listing_id in by_id and r.listing_id not in picked:
            picked.add(r.listing_id)
            valid.append(r)
    valid = valid[:TOP_N]
    top = [{**by_id[r.listing_id], "rank": i, "rank_reason": r.reason} for i, r in enumerate(valid, start=1)]
    return {"top_listings": top}
