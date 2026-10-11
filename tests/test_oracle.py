"""Проверка ВСЕЙ логики без OCR: берём эталонные поля документов, прогоняем через наш validate/classify/
answer и сравниваем с эталоном скриптом организаторов (evaluate.py). Ожидаем 1.0 по всем метрикам.
Если тест падает, ошибка в правилах/ответах, а не в распознавании."""
import importlib.util
import json

from dekanat.core.config import ROOT, load_doc_types
from dekanat.core.export import export_document, export_results
from dekanat.core.pipeline import Pipeline
from dekanat.core.reason import validate
from dekanat.core.schemas import NOT_FOUND, Card, FieldResult

EVAL = ROOT / "data/eval"


def _evaluator():
    spec = importlib.util.spec_from_file_location("evaluate_org", ROOT / "scripts/evaluate.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build_predictions():
    ref = json.loads((EVAL / "reference_results.json").read_text(encoding="utf-8"))
    questions = json.loads((EVAL / "questions.json").read_text(encoding="utf-8"))
    by_doc = {}
    for q in questions:
        by_doc.setdefault(q["document_id"], []).append(q)
    types = load_doc_types()
    pipe = Pipeline()
    docs = []
    for d in ref["documents"]:
        dt = types[d["document_type"]]
        fields = {}
        for k, v in d["fields"].items():
            fields[k] = (FieldResult(value=v, status="found", confidence=1.0)
                         if v != NOT_FOUND else FieldResult())
        card = Card(doc_type=dt.id, fields=fields)
        validation = validate(card, dt)
        answers = [pipe.answer(card, validation, dt, q["question"], q["question_id"])
                   for q in by_doc[d["document_id"]]]
        docs.append(export_document(d["document_id"], card, dt, validation, answers))
    return ref, export_results(docs)


def test_logic_matches_reference_on_all_open_documents():
    ev = _evaluator()
    ref, pred = build_predictions()
    report = ev.evaluate(ref, pred)
    assert report["format_valid"]
    assert report["documents"] == 30 and report["questions"] == 120
    assert report["errors"] == [], report["errors"][:5]
    assert report["field_accuracy_macro"] == 1.0
    assert report["validation_exact_match"] == 1.0
    assert report["question_exact_match"] == 1.0


def test_output_matches_json_schema():
    jsonschema = __import__("pytest").importorskip("jsonschema")
    schema = json.loads((EVAL / "results.schema.json").read_text(encoding="utf-8"))
    _, pred = build_predictions()
    jsonschema.validate(pred, schema)
