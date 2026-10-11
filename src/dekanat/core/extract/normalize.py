"""Нормализация значений по правилам README: даты -> YYYY-MM-DD, курс -> строка с целым числом."""
from __future__ import annotations

import re
from datetime import date

MONTHS = {"января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
          "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12}
_MONTH_RE = "|".join(MONTHS)

# OCR часто путает цифры с буквами внутри дат: О -> 0, l/I -> 1
_OCR_DIGITS = str.maketrans({"O": "0", "О": "0", "o": "0", "о": "0", "l": "1", "I": "1", "|": "1"})
_NUM_TOKEN = r"[0-9OОoоlI|]{1,2}"
_YEAR_TOKEN = r"[0-9OОoоlI|]{2,4}"
DATE_NUM = re.compile(rf"(?<![\w])({_NUM_TOKEN})\s*[./\-]\s*({_NUM_TOKEN})\s*[./\-]\s*({_YEAR_TOKEN})(?![\w])")
DATE_TXT = re.compile(rf"(?<![\w])(\d{{1,2}})\s+({_MONTH_RE})\s+(\d{{4}})(?:\s*г(?:ода|\.|\b))?", re.IGNORECASE)
DATE_ISO = re.compile(r"(?<![\w])(\d{4})-(\d{2})-(\d{2})(?![\w])")


def _iso(y: int, m: int, d: int) -> str | None:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def find_dates(text: str) -> list[tuple[int, str]]:
    """Все даты в тексте в порядке появления: [(позиция, 'YYYY-MM-DD')]. Некорректные пропускаем."""
    found: list[tuple[int, str]] = []
    for m in DATE_ISO.finditer(text):
        iso = _iso(int(m[1]), int(m[2]), int(m[3]))
        if iso:
            found.append((m.start(), iso))
    for m in DATE_NUM.finditer(text):
        d, mo, y = (g.translate(_OCR_DIGITS) for g in m.groups())
        if not (d.isdigit() and mo.isdigit() and y.isdigit()):
            continue
        yi = int(y)
        if len(y) == 2:
            yi += 2000
        iso = _iso(yi, int(mo), int(d))
        if iso:
            found.append((m.start(), iso))
    for m in DATE_TXT.finditer(text):
        iso = _iso(int(m[3]), MONTHS[m[2].lower()], int(m[1]))
        if iso:
            found.append((m.start(), iso))
    found.sort()
    # убираем дубли от пересекающихся шаблонов
    out, seen = [], set()
    for pos, iso in found:
        if (pos, iso) not in seen:
            seen.add((pos, iso))
            out.append((pos, iso))
    return out


_ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6"}
_WORDS = {"первый": "1", "второй": "2", "третий": "3", "четвертый": "4", "четвёртый": "4",
          "пятый": "5", "шестой": "6", "первого": "1", "второго": "2", "третьего": "3",
          "четвертого": "4", "четвёртого": "4", "пятого": "5", "шестого": "6"}


def normalize_course(text: str) -> str | None:
    """«2 курс», «II», «второй» -> '2'."""
    t = text.strip().lower()
    m = re.search(r"\b([1-9])\b", t)
    if m:
        return m.group(1)
    for w, n in _WORDS.items():
        if w in t:
            return n
    m = re.search(r"\b(vi|iv|v|iii|ii|i)\b", t, re.IGNORECASE)
    return _ROMAN.get(m.group(1).upper()) if m else None


def clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s.strip(" \t,;:|_—–-")
