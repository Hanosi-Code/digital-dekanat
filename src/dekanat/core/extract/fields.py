"""Заполнение карточки правилами (якоря + регулярки + нормализация) по конфигу типа документа."""
from __future__ import annotations

import re
from typing import Optional

import numpy as np

from ..config import DocField, DocType, Settings
from ..ocr import Line
from ..schemas import Card, FieldResult
from .normalize import clean_text, find_dates, normalize_course
from .stamp_signature import detect_signature, detect_stamp

LABEL_LIKE = re.compile(r"^\s*[А-ЯЁA-Z][А-Яа-яЁёA-Za-z ./()\-]{1,40}:")     # строка «Метка: ...»
INLINE_LABEL = re.compile(r"\s{2,}|\s+(?=[А-ЯЁ][А-Яа-яЁё ]{2,30}:)")          # следующая метка в той же строке
NUM_TOKEN = re.compile(r"[\w][\w\-/.]*")


def anchor_end(text: str, anchor: str) -> Optional[int]:
    """Позиция начала ЗНАЧЕНИЯ после якоря или None.

    Якорь совпадает с начала слова и «дотягивается» до конца слова. Если дальше в строке стоит двоеточие
    метки («Направление подготовки: ...»), значение начинается после него: остаток самой метки
    («подготовки:») значением быть не может, поэтому пустое поле остаётся пустым."""
    if anchor.startswith("re:"):
        m = re.search(anchor[3:], text, re.IGNORECASE)
        return m.end() if m else None
    m = re.search(r"(?<!\w)" + re.escape(anchor), text, re.IGNORECASE)
    if not m:
        return None
    end = m.end()
    while end < len(text) and text[end].isalnum():
        end += 1
    colon = re.match(r"[^:\n\d]{0,40}:", text[end:])
    if colon:
        end += colon.end()
    return end


def _hits(lines: list[Line], anchors: list[str]):
    """Якоря идут по приоритету: сначала первый якорь по всем строкам, потом второй и т.д."""
    for a in anchors:
        for i, ln in enumerate(lines):
            end = anchor_end(ln.text, a)
            if end is not None:
                yield i, end


def _window(lines: list[Line], i: int, end: int) -> str:
    """Текст после якоря; если в строке пусто, добавляем следующую (если она не «Метка: ...»)."""
    rest = lines[i].text[end:]
    if len(rest.strip(" :—–-.\t")) < 2 and i + 1 < len(lines) and not LABEL_LIKE.match(lines[i + 1].text):
        rest += "\n" + lines[i + 1].text
    elif i + 1 < len(lines) and not LABEL_LIKE.match(lines[i + 1].text):
        rest += "\n" + lines[i + 1].text            # даты периода могут переноситься на следующую строку
    return rest


def _extract_text(window: str) -> Optional[str]:
    first = window.split("\n")[0].lstrip(" :—–-.\t")
    if len(first.strip()) < 2 and "\n" in window:
        first = window.split("\n")[1]
    first = INLINE_LABEL.split(first.strip())[0]
    val = clean_text(first)
    return val if len(val) >= 2 else None


def _extract_number(window: str) -> Optional[str]:
    rest = window.split("\n")[0].lstrip(" :№#—–-.\t")
    m = NUM_TOKEN.match(rest)
    if not m:
        return None
    tok = m.group(0).rstrip(".")
    return tok if any(ch.isdigit() for ch in tok) else None


def _extract_course(lines: list[Line], f: DocField) -> Optional[tuple[str, Line]]:
    for ln in lines:                                   # «2 курс»
        m = re.search(r"(?<![\w])(\d|I{1,3}|IV|V|VI)\s*[- ]?\s*курс", ln.text, re.IGNORECASE)
        if m:
            v = normalize_course(m.group(1))
            if v:
                return v, ln
    for i, end in _hits(lines, f.anchors):             # «Курс: 2»
        v = normalize_course(_window(lines, i, end).split("\n")[0][:25])
        if v:
            return v, lines[i]
    return None


def _extract_one(f: DocField, lines: list[Line]) -> FieldResult:
    if f.kind == "course":
        res = _extract_course(lines, f)
        if res:
            return FieldResult(value=res[0], status="found", confidence=round(res[1].conf, 2),
                               bbox=list(res[1].bbox))
        return FieldResult()

    plans: list[tuple[list[str], int]] = [(f.anchors, 0 if f.range_anchors else f.index)]
    if f.range_anchors:
        plans = [(f.anchors, 0), (f.range_anchors, f.index)]

    for anchors, idx in plans:
        for i, end in _hits(lines, anchors):
            win = _window(lines, i, end)
            value: Optional[str] = None
            if f.kind == "date":
                dates = find_dates(win)
                value = dates[idx][1] if len(dates) > idx else None
            elif f.kind == "number":
                value = _extract_number(win)
            else:
                value = _extract_text(win)
            if value:
                ln = lines[i]
                return FieldResult(value=value, status="found", confidence=round(ln.conf, 2),
                                   bbox=list(ln.bbox))
    return FieldResult()


def _label_bbox(line: Line) -> Optional[list[int]]:
    """Рамка метки «Подпись ...:» — от слова «Подпись» до слова с двоеточием (не дальше 4 слов).

    Фраза без двоеточия («Подпись и печать являются учебными макетами» в сноске) меткой НЕ считается:
    иначе при нечитаемой настоящей метке подпись искалась бы внизу страницы, у сноски."""
    words = sorted((w for w in line.words if w.conf >= 0.5), key=lambda w: w.bbox[0])
    start = next((i for i, w in enumerate(words) if w.text.lower().startswith("подпис")), None)
    if start is None:
        return None
    end = next((j for j in range(start, min(start + 4, len(words))) if words[j].text.endswith(":")), None)
    if end is None:
        return None
    ws = words[start:end + 1]
    return [min(w.bbox[0] for w in ws), min(w.bbox[1] for w in ws),
            max(w.bbox[2] for w in ws), max(w.bbox[3] for w in ws)]


def extract_card(doc_type: DocType, lines: list[Line], image: np.ndarray,
                 settings: Settings) -> Card:
    min_conf = settings.confidence.get("min_field", 0.35)
    det = settings.detectors
    confident = [w.bbox for ln in lines for w in ln.words if w.conf >= 0.5]
    fields: dict[str, FieldResult] = {}
    seal_bbox = None
    # печать считаем первой: её рамка исключается из области поиска подписи
    for f in doc_type.fields:
        if f.kind == "bool" and f.detector == "seal":
            res = detect_stamp(image, det.get("stamp_min_blue_ratio", 0.002))
            fields[f.id] = res
            if res.value and res.bbox:
                seal_bbox = res.bbox
    for f in doc_type.fields:
        if f.id in fields:
            continue
        if f.kind == "bool":
            label = None
            for i, _ in _hits(lines, f.anchors) if f.anchors else []:
                label = _label_bbox(lines[i])
                if label:
                    break
            boxes = confident
            if label:
                # Справа от метки на строке подписи печатного текста не бывает: любое «слово» OCR там
                # (даже уверенное) — это росчерк или линейка. Его нельзя стирать как текст.
                boxes = [b for b in confident
                         if not (b[0] >= label[2] and b[3] >= label[1] and b[1] <= label[3])]
            res = detect_signature(image, det.get("signature_min_ink_ratio", 0.0002), label, boxes,
                                   [seal_bbox] if seal_bbox else None)
        else:
            res = _extract_one(f, lines)
            if res.found and (res.confidence or 0) < min_conf:
                res = FieldResult()          # лучше «не найдено», чем угадывание (п. 2.2 Положения)
        fields[f.id] = res
    return Card(doc_type=doc_type.id, fields=fields, raw_text="\n".join(l.text for l in lines))
