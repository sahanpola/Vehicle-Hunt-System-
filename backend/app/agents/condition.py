"""condition agent (LLM per listing): judge each car's condition from its ad text."""
import asyncio
import json
import logging

from pydantic import BaseModel, Field

from app.agents.llm import ask
from app.agents.state import Listing, PipelineState, compact

log = logging.getLogger(__name__)

MAX_CONCURRENT = 5


class ConditionAssessment(BaseModel):
    condition_score: int = Field(ge=1, le=10, description="1 = poor, 10 = excellent; 5 if the ad gives no detail")
    highlights: list[str] = Field(description="Positive points, e.g. 'single owner', 'full service history'")
    red_flags: list[str] = Field(description="Concerns, e.g. 'accident repaired', 'very high mileage'")


SYSTEM = (
    "You inspect used-car ads. Judge the vehicle's condition only from the given fields: year, "
    "mileage, owners, service history, accident or repair mentions, modifications, and wording. "
    "Keep each highlight or red flag under 8 words."
)


# Search-page cards have no seller text, so an LLM call would only restate year and mileage.
NO_DETAILS = {"condition_score": 5, "highlights": [], "red_flags": ["no seller details (search-page card)"]}


async def _assess(listing: Listing, sem: asyncio.Semaphore) -> tuple[str, dict]:
    if not listing["description"]:
        return listing["id"], NO_DETAILS
    async with sem:
        try:
            prompt = json.dumps(compact(listing), ensure_ascii=False)
            result = await ask(SYSTEM, prompt, ConditionAssessment, effort="low")
            return listing["id"], result.model_dump()
        except Exception:
            log.exception("condition check failed for %s", listing["url"])
            return listing["id"], {"condition_score": 5, "highlights": [], "red_flags": ["could not assess"]}


async def condition(state: PipelineState) -> dict:
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    results = await asyncio.gather(*(_assess(l, sem) for l in state.get("listings", [])))
    return {"condition": dict(results)}
