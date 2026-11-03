"""Shared OpenAI helper: every LLM agent calls `ask()` and gets back a validated Pydantic object."""
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)

_client: AsyncOpenAI | None = None


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=get_settings().openai_api_key or None)
    return _client


def _is_reasoning_model(model: str) -> bool:
    return model.startswith(("gpt-5", "o1", "o3", "o4"))


class LLMRefusal(RuntimeError):
    pass


async def ask(system: str, prompt: str, output: type[T], effort: str = "medium") -> T:
    """One structured-output call (OpenAI Responses API).

    `effort` is the reasoning effort ("low" | "medium" | "high"); it is only sent to
    reasoning models (gpt-5*, o-series) since others reject it.
    """
    settings = get_settings()
    extra = {"reasoning": {"effort": effort}} if _is_reasoning_model(settings.openai_model) else {}
    response = await client().responses.parse(
        model=settings.openai_model,
        instructions=system,
        input=prompt,
        text_format=output,
        max_output_tokens=16000,
        **extra,
    )

    for item in response.output:
        for part in getattr(item, "content", None) or []:
            if part.type == "refusal":
                raise LLMRefusal(f"Model declined the request: {part.refusal}")
    if response.output_parsed is None:
        raise RuntimeError(f"No structured output (status={response.status}, {response.incomplete_details})")
    return response.output_parsed
