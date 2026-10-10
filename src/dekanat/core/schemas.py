"""Единые модели данных. Их используют API, бот, пакетный скрипт и тесты."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

NOT_FOUND = "не найдено"

Verdict = Literal["ok", "missing", "no_data"]


class FieldResult(BaseModel):
    value: Any = None                       # str | bool | None
    status: Literal["found", "not_found"] = "not_found"
    confidence: Optional[float] = None
    bbox: Optional[list[int]] = None        # [x1, y1, x2, y2] в координатах обработанного снимка

    @property
    def found(self) -> bool:
        return self.status == "found"


class Card(BaseModel):
    doc_type: str
    fields: dict[str, FieldResult] = Field(default_factory=dict)
    raw_text: str = ""


class Source(BaseModel):
    type: Literal["regulation", "field"]
    ref: str                                # "3.4" или "issue_date"
    text: Optional[str] = None              # цитата пункта (для regulation)


class Answer(BaseModel):
    verdict: Verdict
    answer: str
    missing_fields: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    card: Card
    answer: Answer
    doc_type_detected: bool = False
    timings_ms: dict[str, int] = Field(default_factory=dict)
