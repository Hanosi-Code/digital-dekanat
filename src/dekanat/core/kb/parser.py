"""Разбор Положения на пронумерованные пункты."""
from __future__ import annotations

import re
from dataclasses import dataclass

CLAUSE_RE = re.compile(r"^\s*(?:п\.?\s*)?(\d+(?:\.\d+)+)[.)]?\s+(\S.*)$", re.IGNORECASE)


@dataclass
class Clause:
    id: str      # "3.4"
    text: str


def parse_regulation(text: str) -> list[Clause]:
    """Строка, начинающаяся с «3.4», открывает пункт; остальные строки — его продолжение.
    TODO: подогнать под реальный формат Положения (подпункты «а)», заголовки разделов и т.д.)."""
    clauses: list[Clause] = []
    for raw in text.splitlines():
        m = CLAUSE_RE.match(raw)
        if m:
            clauses.append(Clause(m.group(1), m.group(2).strip()))
        elif clauses and raw.strip():
            clauses[-1].text += " " + raw.strip()
    return clauses
