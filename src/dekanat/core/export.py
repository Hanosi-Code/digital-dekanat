"""Преобразование внутренних моделей в формат results.json (README, v1.0)."""
from __future__ import annotations

from .config import DocType
from .schemas import NOT_FOUND, Answer, Card, Validation


def export_fields(card: Card, doc_type: DocType) -> dict:
    """Все ключи типа, включая пропуски: текст -> 'не найдено', отметки -> true/false."""
    out: dict = {}
    for f in doc_type.fields:
        r = card.fields.get(f.id)
        if f.kind == "bool":
            out[f.id] = bool(r and r.found and r.value is True)
        else:
            out[f.id] = r.value if (r and r.found and r.value) else NOT_FOUND
    return out


def export_answer(a: Answer) -> dict:
    return {"question_id": a.question_id, "answerable": a.answerable, "value": a.value,
            "answer": a.answer, "sources": a.sources}


def export_document(document_id: str, card: Card, doc_type: DocType, validation: Validation,
                    answers: list[Answer]) -> dict:
    return {
        "document_id": document_id,
        "document_type": doc_type.id,
        "fields": export_fields(card, doc_type),
        "validation": {"status": validation.status, "missing_fields": validation.missing_fields,
                       "sources": validation.sources},
        "answers": [export_answer(a) for a in answers],
    }


def export_results(documents: list[dict]) -> dict:
    return {"version": "1.0", "documents": documents}
