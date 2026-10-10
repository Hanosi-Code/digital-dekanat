"""Единый интерфейс OCR. Любой движок возвращает слова с рамками и уверенностью."""
from __future__ import annotations

from dataclasses import dataclass
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


class OCREngine(Protocol):
    name: str

    def read(self, image: np.ndarray) -> list[Word]: ...


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
                          sum(w.conf for w in ws) / len(ws)))
    lines.sort(key=lambda l: (l.bbox[1], l.bbox[0]))
    return lines
