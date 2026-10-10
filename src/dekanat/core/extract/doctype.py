"""Автоопределение типа документа (бонус): считаем попадания ключевых слов из конфигов."""
from __future__ import annotations

from ..config import DocType


def detect_doc_type(raw_text: str, doc_types: dict[str, DocType]) -> str | None:
    low = raw_text.lower()
    scores = {
        tid: sum(1 for kw in dt.keywords if kw.lower() in low)
        for tid, dt in doc_types.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None
