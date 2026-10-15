from dekanat.core.pipeline import Pipeline
from dekanat.core.schemas import Card


def test_auto_detect_cache_is_reused_with_resolved_type(monkeypatch):
    pipeline = Pipeline()
    calls = {"ocr": 0}

    class FakeOCR:
        def read(self, image):
            calls["ocr"] += 1
            return []

    pipeline._ocr = FakeOCR()
    monkeypatch.setattr("dekanat.core.pipeline.load_images", lambda data, filename: [object()])
    monkeypatch.setattr("dekanat.core.pipeline.preprocess", lambda image, settings: image)
    monkeypatch.setattr("dekanat.core.pipeline.group_lines", lambda words: [])
    monkeypatch.setattr("dekanat.core.pipeline.detect_doc_type",
                        lambda raw, doc_types: "study_certificate")
    monkeypatch.setattr(
        "dekanat.core.pipeline.extract_card",
        lambda doc_type, lines, image, settings: Card(doc_type=doc_type.id),
    )

    data = b"document content"
    pipeline.analyze_document(data, "document.jpg")
    card, _, _, _, timings = pipeline.analyze_document(
        data, "document.jpg", "study_certificate")

    assert card.doc_type == "study_certificate"
    assert calls["ocr"] == 1
    assert "ocr" not in timings
