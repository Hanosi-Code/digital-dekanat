"""Детекторы «есть/нет» для печати и подписи на классическом CV (без нейросетей).
Это стартовые эвристики: подберите пороги на открытых документах."""
from __future__ import annotations

import cv2
import numpy as np

from ..schemas import FieldResult


def detect_stamp(img: np.ndarray, min_blue_ratio: float = 0.002) -> FieldResult:
    """Печать обычно синяя/фиолетовая и круглая. Смотрим цветовую маску + круги."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (95, 60, 40), (150, 255, 255))   # синие/фиолетовые чернила
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    ratio = float(mask.sum() / 255) / mask.size

    bbox = None
    circles_found = False
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        c = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(c)
        if w > 40 and h > 40 and 0.6 < w / h < 1.6:
            circles_found = True
            bbox = [x, y, x + w, y + h]

    present = ratio >= min_blue_ratio and circles_found
    conf = min(1.0, 0.5 + ratio * 50) if present else max(0.3, 0.9 - ratio * 100)
    return FieldResult(value=present, status="found", confidence=round(conf, 2), bbox=bbox)


def detect_signature(img: np.ndarray, min_ink_ratio: float = 0.004,
                     anchor_bbox: list[int] | None = None) -> FieldResult:
    """Подпись = рукописные тёмные контуры. Если известна рамка слова «Подпись»,
    ищем рядом с ней, иначе в нижней трети страницы."""
    h, w = img.shape[:2]
    if anchor_bbox:
        x1, y1, x2, y2 = anchor_bbox
        roi = img[max(0, y1 - 40): min(h, y2 + 80), max(0, x1 - 20): min(w, x2 + 400)]
        origin = (max(0, x1 - 20), max(0, y1 - 40))
    else:
        roi = img[int(h * 0.65):, :]
        origin = (0, int(h * 0.65))
    if roi.size == 0:
        return FieldResult(value=False, status="found", confidence=0.3)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    ratio = float(ink.sum() / 255) / ink.size
    present = ratio >= min_ink_ratio
    # TODO: отделять печатный текст от рукописного (длина штрихов, площадь связных компонент)
    return FieldResult(value=present, status="found",
                       confidence=0.55 if present else 0.5,
                       bbox=[origin[0], origin[1], origin[0] + roi.shape[1], origin[1] + roi.shape[0]])
