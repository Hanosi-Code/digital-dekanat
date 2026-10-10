from dekanat.core.kb.parser import parse_regulation
from dekanat.core.kb.retriever import Retriever

TEXT = """
3.2. Справка должна содержать ФИО студента и период обучения.
3.4. Справка должна содержать номер и дату выдачи, подпись и печать вуза.
Справка без печати не принимается.
5.1. Заявление подаётся на имя ректора.
"""


def test_parse_multiline():
    cl = parse_regulation(TEXT)
    assert [c.id for c in cl] == ["3.2", "3.4", "5.1"]
    assert "не принимается" in cl[1].text


def test_search_finds_right_clause():
    kb = Retriever(parse_regulation(TEXT))
    hits = kb.search("нужна ли печать на справке")
    assert hits and hits[0].clause.id == "3.4"


def test_search_unrelated_has_low_coverage():
    kb = Retriever(parse_regulation(TEXT))
    hits = kb.search("сколько стоит обучение")
    assert not hits or hits[0].coverage < 0.4
