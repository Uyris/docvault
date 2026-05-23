"""Prompt construction for grounded, citable answers.

The retrieved chunks are numbered ``[1]..[k]`` and the model is told to answer
*only* from them and to cite the numbers it used. That contract is what lets us
(a) map citations back to real document offsets and (b) measure faithfulness —
an answer with no support in the context is a hallucination waiting to happen.
"""

from __future__ import annotations

from app.services.vector_store import Retrieved

RAG_SYSTEM_PROMPT = (
    "You are DocVault, a precise question-answering assistant that answers "
    "strictly from the provided sources.\n"
    "Rules:\n"
    "1. Use ONLY the information in the numbered sources below. Do not rely on "
    "prior knowledge.\n"
    "2. Cite the sources you use with bracketed numbers like [1] or [2][3], "
    "placed right after the claim they support.\n"
    "3. If the sources do not contain the answer, say so plainly: "
    '"I could not find this in the provided documents." Do not invent facts.\n'
    "4. Be concise and factual. Answer in the same language as the question."
)


def build_context_block(contexts: list[Retrieved]) -> str:
    """Render retrieved chunks as a numbered, model-readable source list."""
    blocks = []
    for i, r in enumerate(contexts, start=1):
        loc = f" (page {r.chunk.page})" if r.chunk.page else ""
        blocks.append(f"[{i}] {r.chunk.document.filename}{loc}:\n{r.chunk.content}")
    return "\n\n".join(blocks)


def build_user_prompt(question: str, contexts: list[Retrieved]) -> str:
    sources = build_context_block(contexts)
    return (
        f"Sources:\n{sources}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the sources above, citing them with [n]:"
    )
