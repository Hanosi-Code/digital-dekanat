"""Тексты ответов (формулировки из разд. 6 Положения) и структурированные значения для автопроверки."""
from __future__ import annotations

from .config import DocType
from .reason import Decision
from .schemas import (DECISION_MAKER, NO_INFO_TEXT, NOT_FOUND, Answer, Card, Validation)

DISCLAIMER = "Окончательное решение принимает сотрудник деканата. 👩‍🎓"


def _rules(sources: list[str]) -> str:
    nums = [s.split(":", 1)[1] for s in sources if s.startswith("rule:")]
    return ", ".join(nums)


def _field_value(value: object) -> tuple[str, str]:
    if isinstance(value, bool):
        return ("есть" if value else "нет",
                "✅ есть" if value else "❌ нет")
    text = str(value)
    return text, text


def build_answer(d: Decision, card: Card, doc_type: DocType, validation: Validation,
                 question_id: str | None = None) -> Answer:
    labels = {f.id: f.label for f in doc_type.fields}

    if d.intent == "completeness":
        required = [f for f in doc_type.fields if f.required]
        present = [f.label for f in required if f.id not in validation.missing_fields]
        missing = [f.label for f in required if f.id in validation.missing_fields]
        checklist = []
        if present:
            checklist.append(f"✅ Есть: {', '.join(present)}.")
        if missing:
            checklist.append(f"❌ Нет: {', '.join(missing)}.")
        checklist_text = "\n" + "\n".join(checklist) if checklist else ""
        if validation.status == "document_ok":
            text = (f"✅ Документ содержит все обязательные сведения, предусмотренные пунктами "
                    f"{_rules(validation.sources)} Положения.{checklist_text}\n{DISCLAIMER}")
        else:
            miss = ", ".join(labels[m].lower() for m in validation.missing_fields)
            text = (f"⚠️ В документе отсутствуют обязательные сведения: {miss}. "
                    f"Указанные сведения требуются в соответствии с пунктами "
                    f"{_rules(validation.sources)} Положения.{checklist_text}\n{DISCLAIMER}")
        return Answer(question_id=question_id, intent="completeness", answerable=True,
                      value=validation.status, answer=text, sources=list(validation.sources))

    if d.intent == "decision_maker":
        return Answer(question_id=question_id, intent="decision_maker", answerable=True,
                      value=DECISION_MAKER, sources=["rule:1.3"],
                      answer="🏛️ Окончательное решение о принятии документа принимает сотрудник "
                             "деканата (п. 1.3 Положения). Сервис осуществляет только "
                             "предварительную проверку. 🔍")

    if d.intent == "field" and (d.field_id or d.field_ids):
        field_ids = d.field_ids or [d.field_id]
        found: list[tuple[str, str, str]] = []
        missing: list[str] = []
        for fid in field_ids:
            if fid is None:
                continue
            r = card.fields.get(fid)
            if r and r.found and r.value not in (None, "", NOT_FOUND):
                val, display_val = _field_value(r.value)
                found.append((fid, val, display_val))
            else:
                missing.append(labels[fid])

        if len(field_ids) > 1:
            if found:
                value = "; ".join(f"{labels[fid]}: {val}" for fid, val, _ in found)
                display_value = "; ".join(
                    f"{labels[fid]}: {display_val}" for fid, _, display_val in found
                )
                answer = f"📄 Найденные значения: {display_value}."
                if missing:
                    answer += f" Не удалось распознать: {', '.join(missing)}."
                return Answer(question_id=question_id, intent="field", answerable=True, value=value,
                              answer=answer,
                              sources=[f"field:{fid}" for fid, _, _ in found])
            return Answer(question_id=question_id, intent="field", answerable=False, value=None,
                          answer=f"🔎 Сведения по полям {', '.join(missing)} не обнаружены: "
                                 "они не заполнены либо не поддаются распознаванию. "
                                 "Окончательное решение принимает сотрудник деканата. 👩‍🎓",
                          sources=[])

        fid = field_ids[0]
        if fid is None:
            return Answer(question_id=question_id, intent="no_info", answerable=False, value=None,
                          answer=NO_INFO_TEXT, sources=[])
        label = labels[fid]
        if found:
            val, display_val = found[0][1:]
            return Answer(question_id=question_id, intent="field", answerable=True, value=val,
                          answer=f"📄 {label}: {display_val}.", sources=[f"field:{fid}"])
        return Answer(question_id=question_id, intent="field", answerable=False, value=None,
                      answer=f"🔎 Сведения по полю «{label}» не обнаружены: поле не заполнено "
                             "либо не поддаётся распознаванию. Окончательное решение принимает "
                             "сотрудник деканата. 👩‍🎓", sources=[])

    return Answer(question_id=question_id, intent="no_info", answerable=False, value=None,
                  answer=NO_INFO_TEXT, sources=[])