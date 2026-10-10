"""Поиск пунктов Положения. BM25 на лёгкой «стемминг-обрезке» без внешних зависимостей.
Позже можно заменить на pymorphy3 / эмбеддинги (multilingual-e5-small), сохранив интерфейс."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .parser import Clause

STOP = {"и", "в", "на", "по", "с", "к", "о", "а", "но", "или", "не", "что", "как", "ли", "ее",
        "её", "для", "из", "от", "до", "за", "это", "мне", "мой", "моя", "есть", "ли", "же",
        "бы", "при", "под", "ну", "будет", "можно", "нужно", "ли"}
TOKEN_RE = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)


def tokens(text: str) -> list[str]:
    out = []
    for t in TOKEN_RE.findall(text.lower()):
        if t in STOP or len(t) < 2:
            continue
        out.append(t[:5])           # грубый стемминг: русская морфология в основном в окончаниях
    return out


@dataclass
class Hit:
    clause: Clause
    bm25: float
    coverage: float   # 0..1 — доля (взвешенная по idf) слов запроса, найденных в пункте


class Retriever:
    def __init__(self, clauses: list[Clause], k1: float = 1.5, b: float = 0.75):
        self.clauses = clauses
        self.k1, self.b = k1, b
        self.docs = [tokens(c.id + " " + c.text) for c in clauses]
        self.avgdl = (sum(len(d) for d in self.docs) / len(self.docs)) if self.docs else 0
        df: dict[str, int] = {}
        for d in self.docs:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.max_idf = math.log(1 + n + 0.5) if n else 1.0

    def by_id(self, clause_id: str) -> Clause | None:
        return next((c for c in self.clauses if c.id == clause_id), None)

    def search(self, query: str, top_k: int = 3) -> list[Hit]:
        q = tokens(query)
        if not q or not self.docs:
            return []
        total_w = sum(self.idf.get(t, self.max_idf) for t in q)
        hits: list[Hit] = []
        for clause, doc in zip(self.clauses, self.docs):
            tf: dict[str, int] = {}
            for t in doc:
                tf[t] = tf.get(t, 0) + 1
            score = 0.0
            matched_w = 0.0
            for t in q:
                if t in tf:
                    idf = self.idf[t]
                    f = tf[t]
                    score += idf * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * len(doc) / (self.avgdl or 1)))
                    matched_w += idf
            if matched_w:
                hits.append(Hit(clause, score, matched_w / total_w if total_w else 0.0))
        hits.sort(key=lambda h: h.bm25, reverse=True)
        return hits[:top_k]
