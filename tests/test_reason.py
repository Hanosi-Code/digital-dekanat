from dekanat.core.answer import build_answer
from dekanat.core.config import load_doc_types
from dekanat.core.kb.parser import parse_regulation
from dekanat.core.kb.retriever import Retriever
from dekanat.core.reason import decide
from dekanat.core.schemas import Card, FieldResult

REG = """
3.2. Справка содержит ФИО, название вуза, направление, форму и период обучения.
3.4. Справка содержит номер и дату выдачи, подпись и печать вуза.
"""
DT = load_doc_types()["study_certificate"]
KB = Retriever(parse_regulation(REG))


def card(**overrides):
    fields = {}
    for f in DT.fields:
        fields[f.id] = FieldResult(value=True if f.kind == "bool" else "x", status="found",
                                   confidence=0.9)
    for k, v in overrides.items():
        fields[k] = v
    return Card(doc_type=DT.id, fields=fields)


def run(q, c):
    d = decide(q, c, DT, KB)
    return d, build_answer(d, c, DT, KB)


def test_ok():
    d, a = run("Хватит ли справки для перевода?", card())
    assert a.verdict == "ok" and "сотрудник деканата" in a.answer


def test_missing_date_and_stamp():
    c = card(issue_date=FieldResult(), stamp=FieldResult(value=False, status="found"))
    d, a = run("Хватит ли справки для перевода на 2 курс?", c)
    assert a.verdict == "missing"
    assert set(a.missing_fields) == {"issue_date", "stamp"}
    assert any(s.ref == "3.4" for s in a.sources)      # ссылка на реальный пункт


def test_no_data():
    d, a = run("Сколько стоит обучение?", card())
    assert a.verdict == "no_data" and not a.sources


def test_field_question():
    d, a = run("Какая дата выдачи справки?", card(issue_date=FieldResult(
        value="01.09.2024", status="found", confidence=0.9)))
    assert a.verdict == "ok" and "01.09.2024" in a.answer
