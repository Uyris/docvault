"""Load the gold evaluation dataset and its companion document."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"


@dataclass
class EvalItem:
    id: str
    question: str
    reference_answer: str
    answerable: bool


@dataclass
class EvalDataset:
    document_filename: str
    items: list[EvalItem]


def load_dataset() -> EvalDataset:
    raw = json.loads((_DATA_DIR / "eval_dataset.json").read_text(encoding="utf-8"))
    items = [
        EvalItem(
            id=i["id"],
            question=i["question"],
            reference_answer=i.get("reference_answer", ""),
            answerable=bool(i.get("answerable", True)),
        )
        for i in raw["items"]
    ]
    return EvalDataset(document_filename=raw["document"], items=items)


def load_sample_document() -> tuple[str, bytes]:
    """Return (filename, bytes) for the handbook the dataset is written against."""
    ds = json.loads((_DATA_DIR / "eval_dataset.json").read_text(encoding="utf-8"))
    filename = ds["document"]
    return filename, (_DATA_DIR / filename).read_bytes()
