"""Детекторы «есть/нет» для печати и подписи на классическом CV (без нейросетей).
Подлинность не проверяется, только наличие графического элемента (п. 2.3 Положения)."""
from __future__ import annotations

import cv2
import numpy as np

from ..schemas import FieldResult


def detect_stamp(img: np.ndarray, min_blue_ratio: float = 0.002) -> FieldResult:
    """Печать: крупное круглое кольцо синих/фиолетовых чернил. Подпись (узкая и вытянутая) не подходит."""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (95, 50, 40), (150, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    ratio = float(mask.sum() / 255) / mask.size

    best = None
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if min(cw, ch) < 0.07 * w or not (0.75 <= cw / ch <= 1.33):
            continue
        per = cv2.arcLength(c, True)
        circ = 4 * np.pi * cv2.contourArea(c) / (per * per) if per else 0
        if circ >= 0.6 and (best is None or cw * ch > best[2] * best[3]):
            best = (x, y, cw, ch)

    present = best is not None and ratio >= min_blue_ratio
    bbox = [best[0], best[1], best[0] + best[2], best[1] + best[3]] if best else None
    conf = min(1.0, 0.6 + ratio * 40) if present else 0.8
    return FieldResult(value=present, status="found", confidence=round(conf, 2), bbox=bbox)


def detect_signature(img: np.ndarray, min_ink_ratio: float = 0.0002,
                     anchor_bbox: list[int] | None = None,
                     text_boxes: list[tuple[int, int, int, int]] | None = None,
                     exclude_boxes: list[list[int]] | None = None) -> FieldResult:
    """Подпись = рукописный штрих СПРАВА от метки «Подпись ...:».

    anchor_bbox  — рамка самой метки (до двоеточия включительно). Область поиска начинается за ней и
                   ограничена по ширине, чтобы не захватить печать.
    text_boxes   — рамки УВЕРЕННО распознанных слов: напечатанный текст стирается, иначе слово «Подпись»
                   считалось бы подписью. Неуверенные «слова» OCR (рукописный штрих, линейка) не стираем.
    exclude_boxes — например, рамка найденной печати.
    Линейка под подписью (тонкая горизонтальная) подписью не считается.
    min_ink_ratio — минимальная площадь штриха как доля площади страницы."""
    h, w = img.shape[:2]
    if anchor_bbox:
        x1, y1, x2, y2 = anchor_bbox
        rx1, rx2 = min(w, x2 + 10), min(w, x2 + int(0.45 * w))
        ry1, ry2 = max(0, y1 - 70), min(h, y2 + 90)
    else:
        rx1, ry1, rx2, ry2 = 0, int(h * 0.65), w, h
    if rx2 - rx1 < 20 or ry2 - ry1 < 20:
        return FieldResult(value=False, status="found", confidence=0.3)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[ry1:ry2, rx1:rx2]
    thr, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    ink = (gray <= min(thr, 160)).astype(np.uint8) * 255

    for (bx1, by1, bx2, by2) in list(text_boxes or []) + [tuple(b) for b in (exclude_boxes or [])]:
        cv2.rectangle(ink, (bx1 - rx1 - 3, by1 - ry1 - 3), (bx2 - rx1 + 3, by2 - ry1 + 3), 0, -1)

    n, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    area_total, first_bbox = 0, None
    for i in range(1, n):
        x, y, cw, ch, area = stats[i]
        # Линейка «_______» — тонкая прямая: вытянутая И с малой средней толщиной (площадь / длина).
        # Одних пропорций мало: плоский росчерк, слитый с линейкой, тоже вытянут (open-005: 321x37),
        # но его средняя толщина ≈ 9 px против 1–3 px у линейки.
        is_line = cw >= 8 * max(ch, 1) and area / max(cw, ch) <= 3.5
        if area >= 25 and ch >= 8 and not is_line:
            area_total += int(area)
            first_bbox = first_bbox or [rx1 + x, ry1 + y, rx1 + x + cw, ry1 + y + ch]
    # доля от площади СТРАНИЦЫ, а не области поиска: порог не зависит от режима (с меткой / без неё)
    present = area_total / (h * w) >= min_ink_ratio
    return FieldResult(value=present, status="found", confidence=0.7 if present else 0.6,
                       bbox=first_bbox if present else [rx1, ry1, rx2, ry2])
