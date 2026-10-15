"""
Четыре вида вопросов (по открытому набору questions.json):
  completeness   «Содержит ли документ все обязательные сведения?»  -> проверка комплектности
  decision_maker «Кто принимает окончательное решение?»              -> сотрудник деканата, rule:1.3
  field          «Дата», «номер справки», «Укажи значение поля...»    -> значения полей документа
  no_info        всё остальное (стипендия, телефон, кабинет...)      -> answerable=false
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config import DocType
from .kb.retriever import tokens
from .schemas import Card, Intent, Validation

COMPLETENESS_MARKERS = ("все обязательные", "всё обязательное", "обязательные сведения",
                        "комплектн", "хватит", "достаточно", "все ли", "всё ли", "в порядке",
                        "не хватает", "чего не хватает", "проверь документ", "проверить документ")
QUOTED = re.compile(r"[«\"“](.+?)[»\"”]")
GENERIC_FIELD_TOKENS = {"студе"}
FIELD_QUERY_FILLER = {"кака", "како", "знач", "укаж", "назов", "пока", "поле", "поля",
                      "докум", "справ", "какая", "какой", "какое", "какие", "каков",
                      "значе", "укажи", "покаж", "просто"}
BARE_FIELD_TOKENS = {"дата", "даты", "дату", "датой", "когда", "номер", "фио", "печат",
                     "подпи", "форма", "форму", "курс", "групп", "вуз", "напр", "начал",
                     "оконч", "фамил", "имя", "отчес"}
FIELD_SYNONYMS = {"выдан": {"issue_date"}, "получен": {"issue_date"},
                  "фамил": {"student_name"}, "отчес": {"student_name"}}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("ё", "е")).strip()


@dataclass
class Decision:
    intent: Intent
    field_id: str | None = None
    field_ids: list[str] | None = None


def match_field(question: str, doc_type: DocType) -> list[str]:
    """Возвращает совпавшие поля; указанная в кавычках метка должна совпадать точно."""
    quoted = QUOTED.search(question)
    if quoted:
        label = _norm(quoted.group(1))
        for f in doc_type.fields:
            if _norm(f.label) == label:
                return [f.id]
        return []                       # названо поле, которого у этого типа документа нет
    q = set(tokens(question))
    best_matches: list[str] = []
    best_ratio = 0.0
    for f in doc_type.fields:
        lt = set(tokens(f.label)) - GENERIC_FIELD_TOKENS
        overlap = len(q & lt)
        ratio = overlap / len(lt) if lt else 0.0
        if ratio > best_ratio:
            best_matches, best_ratio = [f.id], ratio
        elif ratio and ratio == best_ratio:
            best_matches.append(f.id)
    if best_ratio >= 0.6:
        return best_matches

    synonym_matches = {fid for term, ids in FIELD_SYNONYMS.items() if term in q for fid in ids}
    if synonym_matches:
        return [f.id for f in doc_type.fields if f.id in synonym_matches]

    bare_terms = q - FIELD_QUERY_FILLER
    if len(bare_terms) == 1 and bare_terms <= BARE_FIELD_TOKENS:
        term = next(iter(bare_terms))
        if term in {"дата", "даты", "дату", "датой", "когда"}:
            if "справ" in q:
                return [f.id for f in doc_type.fields if f.id == "issue_date"]
            return [f.id for f in doc_type.fields if f.kind == "date"]
        if term == "номер":
            return [f.id for f in doc_type.fields if f.kind == "number"]
        if term in {"фамил", "имя", "отче"}:
            return [f.id for f in doc_type.fields if f.id == "student_name"]
        return [f.id for f in doc_type.fields if term in set(tokens(f.label))]
    return []


def classify(question: str, doc_type: DocType) -> Decision:
    ql = _norm(question)

    # 1. «Кто принимает окончательное решение...» (проверяем раньше всего: в нём есть слово «принят»)
    if "кто" in ql.split() and ("принима" in ql or "решени" in ql):
        return Decision("decision_maker")

    # 2. Комплектность
    if any(m in ql for m in COMPLETENESS_MARKERS):
        return Decision("completeness")

    # 3. Значение поля
    field_ids = match_field(question, doc_type)
    if field_ids:
        return Decision("field", field_ids[0] if len(field_ids) == 1 else None, field_ids)

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
