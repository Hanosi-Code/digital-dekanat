import json
from collections import Counter
from pathlib import Path

from dekanat.core.answer import build_answer
from dekanat.core.config import ROOT, load_doc_types
from dekanat.core.reason import classify, validate
from dekanat.core.schemas import Card, FieldResult

DT = load_doc_types()
SC = DT["study_certificate"]


def card(dt=SC, **over):
    fields = {}
    for f in dt.fields:
        fields[f.id] = FieldResult(value=True if f.kind == "bool" else "x", status="found", confidence=0.9)
    fields.update(over)
    return Card(doc_type=dt.id, fields=fields)


def ask(q, c=None, dt=SC):
    c = c or card(dt)
    v = validate(c, dt)
    return build_answer(classify(q, dt), c, dt, v, "q1"), v


def test_full_document_lists_all_rules():
    a, v = ask("Содержит ли документ все обязательные сведения по Положению?")
    assert v.status == "document_ok" and v.missing_fields == []
    assert set(v.sources) == {"rule:3.1", "rule:3.2", "rule:3.3"}
    assert a.answerable and a.value == "document_ok" and a.sources == v.sources


def test_missing_only_requirements_for_missing_items():
    c = card(issue_date=FieldResult(), seal_present=FieldResult(value=False, status="found"))
    a, v = ask("Содержит ли документ все обязательные сведения по Положению?", c)
    assert v.status == "missing_fields"
    assert set(v.missing_fields) == {"issue_date", "seal_present"}
    assert set(v.sources) == {"rule:3.1", "rule:3.3"}          # без 3.2: подпись на месте
    assert a.value == "missing_fields" and a.sources == v.sources


def test_decision_maker():
    a, _ = ask("Кто принимает окончательное решение о принятии документа?")
    assert a.value == "сотрудник деканата" and a.answerable and a.sources == ["rule:1.3"]


def test_field_found_and_missing():
    a, _ = ask("Укажи значение поля «Дата выдачи».", card(issue_date=FieldResult(value="2026-09-05", status="found", confidence=.9)))
    assert a.answerable and a.value == "2026-09-05" and a.sources == ["field:issue_date"]
    a, _ = ask("Укажи значение поля «Дата выдачи».", card(issue_date=FieldResult()))
    assert not a.answerable and a.value is None and a.sources == []


def test_field_not_in_this_doc_type_is_no_info():
    a, _ = ask("Укажи значение поля «Учебная группа».")       # у справки об обучении такого поля нет
    assert not a.answerable and a.sources == []


def test_no_info_questions():
    for q in ["Какова стоимость обучения за следующий семестр?", "Какой размер стипендии положен студенту?",
              "Какой срок рассмотрения документа деканатом?", "По какому номеру телефона можно связаться с деканатом?",
              "В каком кабинете принимают оригиналы документов?"]:
        a, _ = ask(q)
        assert not a.answerable and a.value is None and a.sources == [], q
        assert "Обратитесь в деканат" in a.answer


def test_all_open_questions_classified():
    """Все 120 открытых вопросов: 30 комплектность, 30 «кто решает», 30 поле, 30 нет информации."""
    qs = json.loads((ROOT / "data/eval/questions.json").read_text(encoding="utf-8"))
    kinds = Counter()
    for q in qs:
        # без документов тип неизвестен: берём тип, у которого есть поле из вопроса, иначе любой
        best = None
        for dt in DT.values():
            d = classify(q["question"], dt)
            if d.intent == "field":
                best = d
                break
            best = best or d
        kinds[best.intent] += 1
    assert kinds["completeness"] == 30 and kinds["decision_maker"] == 30
    assert kinds["field"] == 30 and kinds["no_info"] == 30
