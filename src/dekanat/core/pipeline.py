"""Единая точка входа: файл + вопрос -> карточка + ответ.
Используется API, ботом (через API) и пакетным скриптом одинаково."""
from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from pathlib import Path

from .answer import build_answer
from .config import ROOT, DocType, Settings, load_doc_types, load_settings
from .extract.doctype import detect_doc_type
from .extract.fields import extract_card
from .ingest import load_images
from .kb.parser import parse_regulation
from .kb.retriever import Retriever
from .ocr import get_engine, group_lines
from .preprocess import preprocess
from .reason import classify, validate
from .schemas import Answer, AnalyzeResponse, Card, Validation


class Pipeline:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or load_settings()
        self.doc_types = load_doc_types()
        self._ocr = None
        self.kb = self._load_kb()
        self._cache: OrderedDict[str, tuple[Card, Validation, str]] = OrderedDict()

    # --- инициализация ---------------------------------------------------------------
    def _load_kb(self) -> Retriever:
        path = ROOT / self.s.regulation.get("file", "data/regulations/rules.md")
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        return Retriever(parse_regulation(text))

    @property
    def ocr(self):
        if self._ocr is None:          # ленивая загрузка: быстрый старт и /health
            self._ocr = get_engine(self.s.ocr_engine, self.s.ocr_lang)
        return self._ocr

    def rule_texts(self, sources: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for src in sources:
            if src.startswith("rule:"):
                c = self.kb.by_id(src.split(":", 1)[1])
                if c:
                    out[c.id] = c.text
        return out

    # --- разбор документа (OCR + карточка + проверка комплектности) ---------------------
    def analyze_document(self, data: bytes, filename: str, doc_type: str | None = None
                         ) -> tuple[Card, Validation, DocType, bool, dict[str, int]]:
        """Тяжёлая часть: выполняется один раз на документ, результат кешируется."""
        t0 = time.perf_counter()
        timings: dict[str, int] = {}
        key = hashlib.sha256(data).hexdigest() + ":" + (doc_type or "auto")
        detected = False

        cached = self._cache.get(key)
        if cached:
            card, validation, _ = cached
            self._cache.move_to_end(key)
        else:
            images = load_images(data, filename)
            img = preprocess(images[0], self.s.preprocess)      # v1.0: одностраничные документы
            timings["preprocess"] = int((time.perf_counter() - t0) * 1000)

            t1 = time.perf_counter()
            lines = group_lines(self.ocr.read(img))
            raw = "\n".join(l.text for l in lines)
            timings["ocr"] = int((time.perf_counter() - t1) * 1000)

            if not doc_type:
                doc_type = detect_doc_type(raw, self.doc_types)
                detected = True
            if doc_type not in self.doc_types:
                raise ValueError("Не удалось определить тип документа, выберите его вручную")

            t2 = time.perf_counter()
            card = extract_card(self.doc_types[doc_type], lines, img, self.s)
            validation = validate(card, self.doc_types[doc_type])
            timings["extract"] = int((time.perf_counter() - t2) * 1000)

            self._cache[key] = (card, validation, raw)
            while len(self._cache) > self.s.cache_size:
                self._cache.popitem(last=False)

        dt = self.doc_types[card.doc_type]
        timings["total"] = int((time.perf_counter() - t0) * 1000)
        return card, validation, dt, detected, timings

    # --- ответ на вопрос (быстрая часть) --------------------------------------------
    def answer(self, card: Card, validation: Validation, doc_type: DocType, question: str,
               question_id: str | None = None) -> Answer:
        return build_answer(classify(question, doc_type), card, doc_type, validation, question_id)

    # --- файл + вопрос -> ответ (бот, API) ---------------------------------------------
    def run(self, data: bytes, filename: str, question: str,
            doc_type: str | None = None) -> AnalyzeResponse:
        card, validation, dt, detected, timings = self.analyze_document(data, filename, doc_type)
        ans = self.answer(card, validation, dt, question)
        return AnalyzeResponse(card=card, validation=validation, answer=ans,
                               rule_texts=self.rule_texts(ans.sources + validation.sources),
                               doc_type_detected=detected, timings_ms=timings)
