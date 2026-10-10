"""Шаблонные ответы. Три вида из кейса: документ в порядке / чего-то не хватает / ответа нет."""
from __future__ import annotations

from .config import DocType
from .kb.retriever import Retriever
from .reason import Decision
from .schemas import NOT_FOUND, Answer, Card

DISCLAIMER = "Окончательное решение примет сотрудник деканата."


def _refs(ids: list[str]) -> str:
    return ", ".join(f"п. {i}" for i in ids)


def build_answer(d: Decision, card: Card, doc_type: DocType, kb: Retriever) -> Answer:
    labels = {f.id: f.label for f in doc_type.fields}

    if d.verdict == "no_data":
        return Answer(
            verdict="no_data",
            answer=("В документе и в Положении нет информации по этому вопросу. "
                    "Обратитесь в деканат."),
        )

    if d.kind == "sufficiency":
        if d.verdict == "ok":
            ref = f" Основание: {_refs(d.clause_ids)} Положения." if d.clause_ids else ""
            text = f"Документ содержит все обязательные данные.{ref} {DISCLAIMER}"
        else:
            miss = ", ".join(labels[m].lower() for m in d.missing_fields)
            ref = f" Основание: {_refs(d.clause_ids)} Положения." if d.clause_ids else ""
            text = f"Не хватает: {miss}.{ref} {DISCLAIMER}"
        return Answer(verdict=d.verdict, answer=text, missing_fields=d.missing_fields,
                      sources=d.sources)

    if d.kind == "field":
        fr = card.fields[d.field_id]
        if d.verdict == "ok":
            val = "есть" if fr.value is True else fr.value
            text = f"{labels[d.field_id]}: {val}."
        else:
            text = (f"{labels[d.field_id]}: {NOT_FOUND}. "
                    "Поле не удалось прочитать на снимке, попробуйте переснять документ.")
        return Answer(verdict=d.verdict, answer=text, missing_fields=d.missing_fields,
                      sources=d.sources)

    # regulation
    quotes = "; ".join(f"п. {s.ref}: {s.text}" for s in d.sources if s.type == "regulation")
    return Answer(verdict="ok", answer=f"По Положению — {quotes}", sources=d.sources)
