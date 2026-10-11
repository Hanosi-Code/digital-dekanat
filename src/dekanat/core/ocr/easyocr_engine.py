from __future__ import annotations

import os

import numpy as np

from .base import Word, cluster_line_ids


class EasyOCREngine:
    """EasyOCR (pip install easyocr). Отдаёт ФРАГМЕНТЫ текста, а не слова, поэтому «слово» здесь —
    фрагмент, а строки собираются кластеризацией по вертикальному центру.
    GPU: OCR_GPU=auto (по умолчанию, если доступен CUDA) | 1 | 0."""
    name = "easyocr"

    def __init__(self, lang: str = "rus"):
        import easyocr
        mode = os.environ.get("OCR_GPU", "auto").lower()
        if mode == "auto":
            try:
                import torch
                use_gpu = torch.cuda.is_available()
            except Exception:  # noqa: BLE001
                use_gpu = False
        else:
            use_gpu = mode in ("1", "true", "yes")
        self.reader = easyocr.Reader(["ru", "en"], gpu=use_gpu, verbose=False)

    def read(self, image: np.ndarray) -> list[Word]:
        results = self.reader.readtext(image, paragraph=False)
        boxes, items = [], []
        for box, text, conf in results:
            text = (text or "").strip()
            if not text:
                continue
            xs = [int(p[0]) for p in box]
            ys = [int(p[1]) for p in box]
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
            items.append((text, float(conf)))
        ids = cluster_line_ids(boxes)
        return [Word(t, b, c, ids[i]) for i, ((t, c), b) in enumerate(zip(items, boxes))]
