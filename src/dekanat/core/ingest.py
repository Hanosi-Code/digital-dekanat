"""Приём файла: JPG/PNG/PDF -> список изображений (BGR, numpy)."""
from __future__ import annotations

import cv2
import numpy as np

MAX_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 3
PDF_DPI = 200


class IngestError(ValueError):
    pass


def load_images(data: bytes, filename: str = "") -> list[np.ndarray]:
    if not data:
        raise IngestError("Пустой файл")
    if len(data) > MAX_BYTES:
        raise IngestError("Файл больше 20 МБ")

    if data[:5] == b"%PDF-" or filename.lower().endswith(".pdf"):
        return _pdf_to_images(data)

    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise IngestError("Не удалось прочитать изображение (нужны JPG, PNG или PDF)")
    return [img]


def _pdf_to_images(data: bytes) -> list[np.ndarray]:
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:  # noqa: BLE001
        raise IngestError(f"Не удалось открыть PDF: {e}") from e
    images = []
    for page in list(doc)[:MAX_PDF_PAGES]:
        pix = page.get_pixmap(dpi=PDF_DPI)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        else:
            arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        images.append(arr)
    if not images:
        raise IngestError("В PDF нет страниц")
    return images
