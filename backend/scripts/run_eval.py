"""Run the RAG evaluation suite from the command line.

    cd backend && python scripts/run_eval.py

Requires Postgres + Redis up (``docker compose up -d postgres redis``) and a
valid ``GROQ_API_KEY``. Writes ``backend/eval_report.json`` and prints a summary.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys

# Make the `app` package importable when run as a plain script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.core.logging import configure_logging  # noqa: E402
from app.db.init_db import init_db  # noqa: E402
from app.db.session import dispose_engine  # noqa: E402
from app.eval.runner import run_evaluation  # noqa: E402
from app.services import semantic_cache  # noqa: E402


def _fmt(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "—"


def _print_summary(report: dict) -> None:
    agg = report["aggregates"]
    print("\n" + "=" * 60)
    print("  DocVault — RAG evaluation report")
    print("=" * 60)
    print(f"  generation model : {report['model']}")
    print(f"  judge model      : {report['eval_model']}")
    print(f"  embedding model  : {report['embedding_model']}")
    print(f"  questions        : {report['dataset_size']}")
    print("-" * 60)
    print(f"  faithfulness       : {_fmt(agg['faithfulness'])}")
    print(f"  answer_relevance   : {_fmt(agg['answer_relevance'])}")
    print(f"  context_relevance  : {_fmt(agg['context_relevance'])}")
    print(f"  answer_correctness : {_fmt(agg['answer_correctness'])}  (answerable only)")
    print("=" * 60)
    print(f"  {'id':<5} {'faith':>6} {'a_rel':>6} {'c_rel':>6} {'correct':>8}  question")
    for it in report["items"]:
        print(
            f"  {it['id']:<5} {_fmt(it['faithfulness']):>6} "
            f"{_fmt(it['answer_relevance']):>6} {_fmt(it['context_relevance']):>6} "
            f"{_fmt(it['answer_correctness']):>8}  {it['question'][:48]}"
        )
    print()


async def main() -> None:
    configure_logging()
    await init_db()
    try:
        report = await run_evaluation(reindex=True)
    finally:
        await dispose_engine()
        await semantic_cache.close()

    out_path = pathlib.Path(__file__).resolve().parent.parent / "eval_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _print_summary(report)
    print(f"  full report written to {out_path}\n")


if __name__ == "__main__":
    asyncio.run(main())
