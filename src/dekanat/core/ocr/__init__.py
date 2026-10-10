from __future__ import annotations

from .base import Line, OCREngine, Word, group_lines

__all__ = ["Line", "OCREngine", "Word", "group_lines", "get_engine"]


def get_engine(name: str, lang: str = "rus") -> OCREngine:
    """Фабрика. Чтобы добавить движок: класс с методом read() и строка здесь."""
    if name == "tesseract":
        from .tesseract import TesseractEngine
        return TesseractEngine(lang)
    if name == "easyocr":
        from .easyocr_engine import EasyOCREngine
        return EasyOCREngine(lang)
    # TODO: paddle
    raise ValueError(f"Неизвестный OCR-движок: {name}")
