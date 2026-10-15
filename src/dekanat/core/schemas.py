"""Модели данных. Структура ответа повторяет формат results.json из README организаторов."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

NOT_FOUND = "не найдено"
DECISION_MAKER = "сотрудник деканата"
NO_INFO_TEXT = "К сожалению в документе и в положении нет информации для ответа на этот вопрос. Обратитесь в деканат."

ValidationStatus = Literal["document_ok", "missing_fields"]
Intent = Literal["completeness", "decision_maker", "field", "no_info"]


class FieldResult(BaseModel):
    value: Any = None                       # str (даты уже ISO) | bool | None
    status: Literal["found", "not_found"] = "not_found"
    confidence: Optional[float] = None
    bbox: Optional[list[int]] = None        # [x1, y1, x2, y2] — для подсветки на снимке

    @property
    def found(self) -> bool:
        return self.status == "found"


class Card(BaseModel):
    doc_type: str
    fields: dict[str, FieldResult] = Field(default_factory=dict)
    raw_text: str = ""


class Validation(BaseModel):
    status: ValidationStatus
    missing_fields: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)        # ["rule:3.1", ...]


class Answer(BaseModel):
    question_id: Optional[str] = None
    intent: Intent = "no_info"
    answerable: bool = False
    value: Optional[str] = None
    answer: str
    sources: list[str] = Field(default_factory=list)        # "rule:1.3" | "field:issue_date"


class AnalyzeResponse(BaseModel):
    card: Card
    validation: Validation
    answer: Answer
    rule_texts: dict[str, str] = Field(default_factory=dict)  # "3.1" -> текст пункта (для бота)
    doc_type_detected: bool = False
    timings_ms: dict[str, int] = Field(default_factory=dict)
