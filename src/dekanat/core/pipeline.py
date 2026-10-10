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
from .reason import decide
from .schemas import AnalyzeResponse, Card


class Pipeline:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or load_settings()
        self.doc_types = load_doc_types()
        self._ocr = None
        self.kb = self._load_kb()
        self._cache: OrderedDict[str, tuple[Card, str]] = OrderedDict()

    # --- инициализация ---------------------------------------------------------------
    def _load_kb(self) -> Retriever:
        path = ROOT / self.s.regulation.get("file", "data/regulations/polozhenie.txt")
        if not path.exists():
            alt = path.with_name("polozhenie.sample.txt")
            path = alt if alt.exists() else path
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        return Retriever(parse_regulation(text))

    @property
    def ocr(self):
        if self._ocr is None:          # ленивая загрузка: быстрый старт и /health
            self._ocr = get_engine(self.s.ocr_engine, self.s.ocr_lang)
        return self._ocr

    # --- основной метод --------------------------------------------------------------
    def run(self, data: bytes, filename: str, question: str,
            doc_type: str | None = None) -> AnalyzeResponse:
        t0 = time.perf_counter()
        timings: dict[str, int] = {}

        key = hashlib.sha256(data).hexdigest() + ":" + (doc_type or "auto")
        cached = self._cache.get(key)
        detected = False
        if cached:
            card, _ = cached
        else:
            images = load_images(data, filename)
            img = preprocess(images[0], self.s.preprocess)   # TODO: многостраничные PDF
            timings["preprocess"] = int((time.perf_counter() - t0) * 1000)

            t1 = time.perf_counter()
            words = self.ocr.read(img)
            lines = group_lines(words)
            raw = "\n".join(l.text for l in lines)
            timings["ocr"] = int((time.perf_counter() - t1) * 1000)

            if not doc_type:
                doc_type = detect_doc_type(raw, self.doc_types)
                detected = True
            if doc_type not in self.doc_types:
                raise ValueError("Не удалось определить тип документа, выберите его вручную")

            t2 = time.perf_counter()
            card = extract_card(self.doc_types[doc_type], lines, img, self.s)
            timings["extract"] = int((time.perf_counter() - t2) * 1000)

            self._cache[key] = (card, raw)
            while len(self._cache) > self.s.cache_size:
                self._cache.popitem(last=False)

        dt: DocType = self.doc_types[card.doc_type]
        t3 = time.perf_counter()
        decision = decide(question, card, dt, self.kb,
                          self.s.regulation.get("min_relevance", 0.4))
        answer = build_answer(decision, card, dt, self.kb)
        timings["answer"] = int((time.perf_counter() - t3) * 1000)
        timings["total"] = int((time.perf_counter() - t0) * 1000)
        return AnalyzeResponse(card=card, answer=answer, doc_type_detected=detected,
                               timings_ms=timings)
