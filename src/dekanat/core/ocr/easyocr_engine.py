from __future__ import annotations

import numpy as np

from .base import Word


class EasyOCREngine:
    """Раскомментируйте easyocr в requirements-api.txt. Веса скачайте при сборке образа."""
    name = "easyocr"

    def __init__(self, lang: str = "rus"):
        import easyocr
        self.reader = easyocr.Reader(["ru", "en"], gpu=False)

    def read(self, image: np.ndarray) -> list[Word]:
        words: list[Word] = []
        results = self.reader.readtext(image, paragraph=False)
        # EasyOCR отдаёт фрагменты, а не слова: line_id считаем по вертикальной позиции
        for box, text, conf in results:
            xs = [int(p[0]) for p in box]
            ys = [int(p[1]) for p in box]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            words.append(Word(text, bbox, float(conf), line_id=bbox[1] // 20))
        return words
