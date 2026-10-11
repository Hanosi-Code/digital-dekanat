"""Единый интерфейс OCR. Любой движок возвращает слова с рамками и уверенностью."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass
class Word:
    text: str
    bbox: tuple[int, int, int, int]   # x1, y1, x2, y2
    conf: float                        # 0..1
    line_id: int = 0                   # слова одной строки имеют одинаковый line_id


@dataclass
class Line:
    text: str
    bbox: tuple[int, int, int, int]
    conf: float
    words: list = field(default_factory=list)   # слова строки (для точных рамок)


class OCREngine(Protocol):
    name: str

    def read(self, image: np.ndarray) -> list[Word]: ...


def cluster_line_ids(boxes: list[tuple[int, int, int, int]]) -> list[int]:
    """line_id для фрагментов: фрагменты на одной визуальной строке получают один id.
    Сравнение по вертикальному центру, а не по сетке: нет разрывов на границах ячеек."""
    order = sorted(range(len(boxes)), key=lambda i: (boxes[i][1] + boxes[i][3]) / 2)
    ids = [0] * len(boxes)
    line = -1
    cy = ch = None
    for i in order:
        x1, y1, x2, y2 = boxes[i]
        c, h = (y1 + y2) / 2, max(1, y2 - y1)
        if cy is None or abs(c - cy) > 0.6 * max(h, ch):
            line += 1
            cy, ch = c, h
        else:
            cy = (cy + c) / 2
        ids[i] = line
    return ids


def group_lines(words: list[Word]) -> list[Line]:
    by_line: dict[int, list[Word]] = {}
    for w in words:
        by_line.setdefault(w.line_id, []).append(w)
    lines: list[Line] = []
    for ws in by_line.values():
        ws.sort(key=lambda w: w.bbox[0])
        x1 = min(w.bbox[0] for w in ws)
        y1 = min(w.bbox[1] for w in ws)
        x2 = max(w.bbox[2] for w in ws)
        y2 = max(w.bbox[3] for w in ws)
        lines.append(Line(" ".join(w.text for w in ws), (x1, y1, x2, y2),
                          sum(w.conf for w in ws) / len(ws), list(ws)))
    lines.sort(key=lambda l: (l.bbox[1], l.bbox[0]))
    return lines
