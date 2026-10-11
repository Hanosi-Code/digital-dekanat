"""Регрессия на РЕАЛЬНЫХ документах организаторов (OCR + извлечение + проверка).

Положите PNG в data/open/documents/ (open-001.png ...). Тест сравнивает поля с эталоном
reference_results.json для всех найденных файлов. Нет файлов или нет Tesseract rus -> тест пропускается."""
import json

import pytest

from dekanat.core.config import ROOT

DOCS = ROOT / "data/open/documents"
PNGS = sorted(DOCS.glob("open-*.png")) if DOCS.exists() else []


def _tesseract_rus() -> bool:
    try:
        import pytesseract
        return "rus" in pytesseract.get_languages()
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not PNGS, reason="нет файлов data/open/documents/open-*.png")
@pytest.mark.skipif(not _tesseract_rus(), reason="нужен Tesseract с языком rus")
def test_fields_and_validation_match_reference():
    from dekanat.core.export import export_fields
    from dekanat.core.pipeline import Pipeline

    ref = {d["document_id"]: d for d in json.loads(
        (ROOT / "data/eval/reference_results.json").read_text(encoding="utf-8"))["documents"]}
    pipe = Pipeline()
    mismatches = []
    for png in PNGS:
        did = png.stem
        r = ref[did]
        card, validation, dt, _, _ = pipe.analyze_document(png.read_bytes(), png.name, r["document_type"])
        got = export_fields(card, dt)
        for k, v in r["fields"].items():
            if got[k] != v:
                mismatches.append((did, k, got[k], v))
        if (validation.status != r["validation"]["status"]
                or set(validation.missing_fields) != set(r["validation"]["missing_fields"])
                or set(validation.sources) != set(r["validation"]["sources"])):
            mismatches.append((did, "validation", validation.model_dump(), r["validation"]))
    assert not mismatches, mismatches
