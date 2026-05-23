"""RAG quality metrics.

Measuring a RAG system — not just shipping one — is the point of this module.
We compute the three metrics that catch the failure modes that matter:

* **faithfulness** — is the answer actually grounded in the retrieved sources,
  or did the model make something up? (LLM-as-judge)
* **answer_relevance** — does the answer address the question that was asked?
  (LLM-as-judge)
* **context_relevance** — did retrieval surface chunks that relate to the
  question? (embedding cosine similarity — deterministic, no LLM cost)

We hand-roll these instead of pulling in RAGAS: full control over the prompts,
far lighter dependencies, transparent scores we can explain in a README, and no
second LLM-config surface to manage. The judge runs on a small, cheap model
(``LLM_EVAL_MODEL``) so evaluating a suite stays affordable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger
from app.services import embeddings, llm

log = get_logger(__name__)


@dataclass
class EvalScore:
    score: float  # 0..1
    reasoning: str = ""


def _parse_score(text: str) -> EvalScore:
    try:
        data = json.loads(text)
        score = float(data.get("score", 0.0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return EvalScore(score=0.0, reasoning=f"unparseable judge output: {text[:200]}")
    return EvalScore(score=max(0.0, min(1.0, score)), reasoning=str(data.get("reasoning", "")))


_FAITHFULNESS_SYS = (
    "You are a strict evaluator of factual grounding. Given SOURCES and an "
    "ANSWER, judge how fully the answer's claims are supported by the sources. "
    "1.0 = every claim is directly supported; 0.0 = the answer contradicts or "
    "is unsupported by the sources (hallucination). Ignore citation markers. "
    'Respond ONLY as JSON: {"score": <0..1>, "reasoning": "<one sentence>"}.'
)

_RELEVANCE_SYS = (
    "You are evaluating whether an ANSWER actually addresses a QUESTION. "
    "1.0 = directly and completely answers it; 0.0 = off-topic or evasive. "
    "An honest \"I could not find this in the documents\" is a relevant "
    "response to an unanswerable question and should score high. "
    'Respond ONLY as JSON: {"score": <0..1>, "reasoning": "<one sentence>"}.'
)


async def faithfulness(answer: str, contexts: list[str]) -> EvalScore:
    sources = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(contexts, start=1))
    user = f"SOURCES:\n{sources}\n\nANSWER:\n{answer}"
    result = await llm.complete(
        _FAITHFULNESS_SYS, user, model=settings.llm_eval_model, json_mode=True, temperature=0.0
    )
    return _parse_score(result.text)


async def answer_relevance(question: str, answer: str) -> EvalScore:
    user = f"QUESTION:\n{question}\n\nANSWER:\n{answer}"
    result = await llm.complete(
        _RELEVANCE_SYS, user, model=settings.llm_eval_model, json_mode=True, temperature=0.0
    )
    return _parse_score(result.text)


async def context_relevance(question: str, contexts: list[str]) -> float:
    """Mean cosine similarity between the question and each retrieved chunk."""
    if not contexts:
        return 0.0
    vectors = await embeddings.embed_texts([question, *contexts])
    q = np.asarray(vectors[0], dtype=np.float32)
    ctx = np.asarray(vectors[1:], dtype=np.float32)
    sims = ctx @ q  # normalised vectors → dot product is cosine similarity
    return round(float(np.clip(sims.mean(), 0.0, 1.0)), 4)


async def answer_correctness(answer: str, reference: str) -> float:
    """Semantic similarity to a reference answer (only when ground truth exists)."""
    if not reference:
        return 0.0
    a, b = await embeddings.embed_texts([answer, reference])
    return round(float(np.clip(np.dot(np.asarray(a), np.asarray(b)), 0.0, 1.0)), 4)
