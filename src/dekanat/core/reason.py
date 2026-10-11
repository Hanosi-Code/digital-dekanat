"""Детерминированная логика: никаких генеративных моделей, поэтому нет выдумок.

Четыре вида вопросов (по открытому набору questions.json):
  completeness   «Содержит ли документ все обязательные сведения?»  -> проверка комплектности
  decision_maker «Кто принимает окончательное решение?»              -> сотрудник деканата, rule:1.3
  field          «Укажи значение поля «...»»                         -> значение поля, field:<ключ>
  no_info        всё остальное (стипендия, телефон, кабинет...)      -> answerable=false
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config import DocType
from .kb.retriever import tokens
from .schemas import Card, Intent, Validation

FIELD_Q_MARKERS = ("какой", "какая", "какое", "какие", "когда", "кто", "укажи", "назови", "значение",
                   "покажи", "чему равн", "что указан", "на какой")
COMPLETENESS_MARKERS = ("все обязательные", "всё обязательное", "обязательные сведения",
                        "комплектн", "хватит", "достаточно", "все ли", "всё ли", "в порядке",
                        "не хватает", "чего не хватает", "проверь документ", "проверить документ")
QUOTED = re.compile(r"[«\"“](.+?)[»\"”]")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("ё", "е")).strip()


@dataclass
class Decision:
    intent: Intent
    field_id: str | None = None


def match_field(question: str, doc_type: DocType) -> tuple[str | None, bool]:
    """Возвращает (id поля, было_ли_поле_названо_явно). Явное название — в кавычках «...»."""
    quoted = QUOTED.search(question)
    if quoted:
        label = _norm(quoted.group(1))
        for f in doc_type.fields:
            if _norm(f.label) == label:
                return f.id, True
        return None, True               # названо поле, которого у этого типа документа нет
    q = set(tokens(question))
    best, best_ratio = None, 0.0
    for f in doc_type.fields:
        lt = set(tokens(f.label))
        if lt and (r := len(q & lt) / len(lt)) >= 0.6 and r > best_ratio:
            best, best_ratio = f.id, r
    return best, False


def classify(question: str, doc_type: DocType) -> Decision:
    ql = _norm(question)

    # 1. «Кто принимает окончательное решение...» (проверяем раньше всего: в нём есть слово «принят»)
    if "кто" in ql.split() and ("принима" in ql or "решени" in ql):
        return Decision("decision_maker")

    # 2. Комплектность
    if any(m in ql for m in COMPLETENESS_MARKERS):
        return Decision("completeness")

    # 3. Значение поля
    fid, explicit = match_field(question, doc_type)
    if fid and (explicit or any(m in ql for m in FIELD_Q_MARKERS)):
        return Decision("field", fid)

    # 4. Ни документ, ни Положение ответа не содержат
    return Decision("no_info")


def is_missing(card: Card, fid: str) -> bool:
    r = card.fields.get(fid)
    if r is None or not r.found:
        return True
    return r.value is False             # отметка «нет» = отсутствует (п. 2.3 Положения)


def validate(card: Card, doc_type: DocType) -> Validation:
    """Полный документ: источники — все пункты, устанавливающие обязательные поля и отметки.
    Неполный: только требования к недостающим элементам."""
    required = doc_type.required_fields()
    missing = [f for f in required if is_missing(card, f.id)]
    pool = missing if missing else required
    refs: list[str] = []
    for f in pool:
        for r in f.regulation_refs:
            ref = f"rule:{r}"
            if ref not in refs:
                refs.append(ref)
    return Validation(status="missing_fields" if missing else "document_ok",
                      missing_fields=[f.id for f in missing], sources=refs)
