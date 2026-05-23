"""LLM access (Groq via LangChain).

LangChain is the orchestration layer the roadmap calls for, but we use it
deliberately — ``ChatGroq`` for chat + message primitives — rather than hiding
the pipeline behind opaque chains. Keeping retrieval, prompting and generation
explicit makes the data flow (and the citations) easy to follow and test.

Groq serves open models (Llama 3.x) cheaply and fast, which pairs well with the
semantic cache: the common path is cache; the LLM is the expensive fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str


@lru_cache
def _get_chat(model: str, temperature: float, max_tokens: int, json_mode: bool):
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set — add it to your .env (free key at "
            "https://console.groq.com/keys)."
        )
    from langchain_groq import ChatGroq

    model_kwargs: dict = {}
    if json_mode:
        model_kwargs["response_format"] = {"type": "json_object"}

    return ChatGroq(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=settings.groq_api_key,
        model_kwargs=model_kwargs,
    )


def _extract_usage(message) -> tuple[int, int, int]:
    usage = getattr(message, "usage_metadata", None) or {}
    if usage:
        pt = int(usage.get("input_tokens", 0))
        ct = int(usage.get("output_tokens", 0))
        return pt, ct, int(usage.get("total_tokens", pt + ct))
    # Fallback to provider-native shape.
    token_usage = (getattr(message, "response_metadata", {}) or {}).get("token_usage", {})
    pt = int(token_usage.get("prompt_tokens", 0))
    ct = int(token_usage.get("completion_tokens", 0))
    return pt, ct, int(token_usage.get("total_tokens", pt + ct))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=8), reraise=True)
async def complete(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_mode: bool = False,
) -> LLMResult:
    """Single-turn completion. Retries transient failures with backoff."""
    chat = _get_chat(
        model or settings.llm_model,
        settings.llm_temperature if temperature is None else temperature,
        max_tokens or settings.llm_max_tokens,
        json_mode,
    )
    response = await chat.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    pt, ct, tt = _extract_usage(response)
    return LLMResult(
        text=str(response.content),
        prompt_tokens=pt,
        completion_tokens=ct,
        total_tokens=tt,
        model=model or settings.llm_model,
    )


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost from token counts using the configured per-1M prices."""
    return round(
        prompt_tokens / 1_000_000 * settings.cost_per_1m_input_tokens
        + completion_tokens / 1_000_000 * settings.cost_per_1m_output_tokens,
        8,
    )
