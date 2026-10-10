"""Детерминированная логика ответа: никаких генеративных моделей, поэтому нет выдумок.
Три исхода: ok / missing / no_data. Любая ссылка на пункт проверяется по базе знаний."""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import DocType
from .kb.retriever import Retriever, tokens
from .schemas import Card, Source

SUFFICIENCY_MARKERS = ("хватит", "достаточно", "подойд", "подход", "провер", "все ли", "всё ли",
                       "примут", "принят", "годит", "в порядке", "правильн", "нужно ли что-то")
FIELD_Q_MARKERS = ("какой", "какая", "какое", "когда", "кто", "что указан", "укажи", "назови",
                   "сколько", "на какой")


@dataclass
class Decision:
    verdict: str                                  # ok | missing | no_data
    kind: str                                     # sufficiency | field | regulation | none
    missing_fields: list[str] = field(default_factory=list)
    field_id: str | None = None
    clause_ids: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


def _is_missing(card: Card, fid: str) -> bool:
    r = card.fields.get(fid)
    if r is None or not r.found:
        return True
    return r.value is False            # печать/подпись «нет» тоже считаем отсутствующим


def _match_field(question: str, doc_type: DocType) -> str | None:
    """Поле считается названным в вопросе, если в вопросе есть большая часть слов его названия
    (одно общее слово вроде «обучения» недостаточно: «сколько стоит обучение» — не вопрос о поле)."""
    q = set(tokens(question))
    best, best_ratio = None, 0.0
    for f in doc_type.fields:
        lt = set(tokens(f.label))
        if not lt:
            continue
        ratio = len(q & lt) / len(lt)
        if ratio >= 0.6 and ratio > best_ratio:
            best, best_ratio = f.id, ratio
    return best


def decide(question: str, card: Card, doc_type: DocType, kb: Retriever,
           min_relevance: float = 0.4) -> Decision:
    ql = question.lower()

    # 1. «Хватит ли документа?» — проверяем обязательные поля
    if any(m in ql for m in SUFFICIENCY_MARKERS):
        required = doc_type.required_fields()
        missing = [f for f in required if _is_missing(card, f.id)]
        pool = missing if missing else required
        refs: list[str] = []
        for f in pool:
            for r in f.regulation_refs:
                # ссылаемся только на реально существующие пункты
                if kb.by_id(r) and r not in refs:
                    refs.append(r)
        sources = [Source(type="regulation", ref=r, text=kb.by_id(r).text) for r in refs]
        sources += [Source(type="field", ref=f.id) for f in missing]
        return Decision("missing" if missing else "ok", "sufficiency",
                        [f.id for f in missing], None, refs, sources)

    # 2. Вопрос о значении поля
    fid = _match_field(question, doc_type)
    if fid and any(m in ql for m in FIELD_Q_MARKERS):
        miss = _is_missing(card, fid)
        return Decision("missing" if miss else "ok", "field", [fid] if miss else [], fid, [],
                        [Source(type="field", ref=fid)])

    # 3. Вопрос о правилах — ищем в Положении
    hits = [h for h in kb.search(question, top_k=2) if h.coverage >= min_relevance]
    if hits:
        return Decision("ok", "regulation", [], None, [h.clause.id for h in hits],
                        [Source(type="regulation", ref=h.clause.id, text=h.clause.text)
                         for h in hits])

    # 4. Ни в документе, ни в Положении — честно говорим, что ответа нет
    return Decision("no_data", "none")
