"""Тексты ответов (формулировки из разд. 6 Положения) и структурированные значения для автопроверки."""
from __future__ import annotations

from .config import DocType
from .reason import Decision
from .schemas import (DECISION_MAKER, NO_INFO_TEXT, NOT_FOUND, Answer, Card, Validation)

DISCLAIMER = "Окончательное решение примет сотрудник деканата."


def _rules(sources: list[str]) -> str:
    nums = [s.split(":", 1)[1] for s in sources if s.startswith("rule:")]
    return ", ".join(nums)


def build_answer(d: Decision, card: Card, doc_type: DocType, validation: Validation,
                 question_id: str | None = None) -> Answer:
    labels = {f.id: f.label for f in doc_type.fields}

    if d.intent == "completeness":
        if validation.status == "document_ok":
            text = (f"Документ содержит все обязательные сведения по пунктам {_rules(validation.sources)} "
                    f"Положения. {DISCLAIMER}")
        else:
            miss = ", ".join(labels[m].lower() for m in validation.missing_fields)
            text = (f"Не хватает обязательных сведений: {miss}. Эти сведения требуют пункты "
                    f"{_rules(validation.sources)} Положения. {DISCLAIMER}")
        return Answer(question_id=question_id, intent="completeness", answerable=True,
                      value=validation.status, answer=text, sources=list(validation.sources))

    if d.intent == "decision_maker":
        return Answer(question_id=question_id, intent="decision_maker", answerable=True,
                      value=DECISION_MAKER, sources=["rule:1.3"],
                      answer="Окончательное решение о принятии документа принимает сотрудник деканата "
                             "(п. 1.3 Положения). Сервис выполняет только предварительную проверку.")

    if d.intent == "field" and d.field_id:
        r = card.fields.get(d.field_id)
        label = labels[d.field_id]
        if r and r.found and r.value not in (None, "", NOT_FOUND):
            val = ("есть" if r.value is True else "нет") if isinstance(r.value, bool) else str(r.value)
            if isinstance(r.value, bool) and not r.value:
                return Answer(question_id=question_id, intent="field", answerable=False, value=None,
                              answer=f"В документе не обнаружен графический элемент: {label.lower()}.",
                              sources=[])
            return Answer(question_id=question_id, intent="field", answerable=True, value=val,
                          answer=f"{label}: {val}.", sources=[f"field:{d.field_id}"])
        return Answer(question_id=question_id, intent="field", answerable=False, value=None,
                      answer=f"Поле «{label}» не найдено: оно не заполнено или его не удалось прочитать. "
                             "Окончательное решение примет сотрудник деканата.", sources=[])

    return Answer(question_id=question_id, intent="no_info", answerable=False, value=None,
                  answer=NO_INFO_TEXT, sources=[])
