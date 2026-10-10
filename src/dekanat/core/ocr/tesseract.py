from __future__ import annotations

import numpy as np

from .base import Word


class TesseractEngine:
    name = "tesseract"

    def __init__(self, lang: str = "rus"):
        import pytesseract  # noqa: F401  (проверяем наличие при старте)
        self.lang = lang

    def read(self, image: np.ndarray) -> list[Word]:
        import pytesseract
        from pytesseract import Output

        d = pytesseract.image_to_data(image, lang=self.lang, output_type=Output.DICT,
                                      config="--oem 1 --psm 6")
        words: list[Word] = []
        for i, text in enumerate(d["text"]):
            text = (text or "").strip()
            conf = float(d["conf"][i])
            if not text or conf < 0:
                continue
            x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
            line_id = d["block_num"][i] * 10_000 + d["par_num"][i] * 100 + d["line_num"][i]
            words.append(Word(text, (x, y, x + w, y + h), conf / 100.0, line_id))
        return words
