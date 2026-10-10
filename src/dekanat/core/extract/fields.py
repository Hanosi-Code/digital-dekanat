"""Заполнение карточки: правила (якоря + регулярки) по конфигу типа документа."""
from __future__ import annotations

import re
from typing import Optional

import numpy as np

from ..config import DocField, DocType, Settings
from ..ocr import Line
from ..schemas import Card, FieldResult
from .stamp_signature import detect_signature, detect_stamp

DATE_RE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b")
NUM_RE = re.compile(r"№\s*([\w\-/]+)|\bномер\s*[:№]?\s*([\w\-/]+)", re.IGNORECASE)


def _norm_date(m: re.Match) -> str:
    d, mo, y = m.groups()
    if len(y) == 2:
        y = "20" + y
    return f"{int(d):02d}.{int(mo):02d}.{y}"


def _after(text: str, anchor: str) -> str:
    i = text.lower().find(anchor.lower())
    rest = text[i + len(anchor):] if i >= 0 else text
    return rest.lstrip(" :—–-.").strip()


def _anchor_lines(lines: list[Line], anchors: list[str]) -> list[tuple[int, str]]:
    hits = []
    for i, ln in enumerate(lines):
        low = ln.text.lower()
        for a in anchors:
            if a.lower() in low:
                hits.append((i, a))
                break
    return hits


def _extract_one(f: DocField, lines: list[Line]) -> FieldResult:
    for i, anchor in _anchor_lines(lines, f.anchors):
        ln = lines[i]
        window = ln.text + " " + (lines[i + 1].text if i + 1 < len(lines) else "")
        value: Optional[str] = None

        if f.kind == "date":
            m = DATE_RE.search(window)
            value = _norm_date(m) if m else None
        elif f.kind == "period":
            ds = [_norm_date(m) for m in DATE_RE.finditer(window)]
            value = f"{ds[0]} – {ds[1]}" if len(ds) >= 2 else None
        elif f.kind == "number":
            m = NUM_RE.search(window)
            value = (m.group(1) or m.group(2)) if m else None
        else:  # text
            rest = _after(ln.text, anchor)
            if len(rest) < 3 and i + 1 < len(lines):
                rest = lines[i + 1].text.strip()
            value = rest if len(rest) >= 3 else None

        if value:
            return FieldResult(value=value, status="found",
                               confidence=round(ln.conf, 2), bbox=list(ln.bbox))
    return FieldResult()   # not_found


def extract_card(doc_type: DocType, lines: list[Line], image: np.ndarray,
                 settings: Settings) -> Card:
    min_conf = settings.confidence.get("min_field", 0.35)
    det = settings.detectors
    fields: dict[str, FieldResult] = {}
    for f in doc_type.fields:
        if f.kind == "bool":
            if f.detector == "stamp":
                res = detect_stamp(image, det.get("stamp_min_blue_ratio", 0.002))
            else:
                anchor = _anchor_lines(lines, f.anchors)
                bbox = list(lines[anchor[0][0]].bbox) if anchor else None
                res = detect_signature(image, det.get("signature_min_ink_ratio", 0.004), bbox)
        else:
            res = _extract_one(f, lines)
            if res.found and (res.confidence or 0) < min_conf:
                res = FieldResult()   # лучше «не найдено», чем угадывание
        fields[f.id] = res
    return Card(doc_type=doc_type.id, fields=fields,
                raw_text="\n".join(l.text for l in lines))
