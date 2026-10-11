"""Загрузка settings.yaml и конфигов типов документов."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

ROOT = Path(os.environ.get("DEKANAT_ROOT", Path(__file__).resolve().parents[3]))
CONFIGS = ROOT / "configs"


class DocField(BaseModel):
    id: str
    label: str
    kind: Literal["text", "date", "course", "number", "bool"] = "text"
    required: bool = True
    anchors: list[str] = Field(default_factory=list)          # "re:..." = регулярное выражение
    range_anchors: list[str] = Field(default_factory=list)    # якоря периода «с ... по ...»
    index: int = 0                                            # какая по счёту дата после якоря
    detector: Optional[Literal["seal", "signature"]] = None
    regulation_refs: list[str] = Field(default_factory=list)  # "3.1" (в выдаче: "rule:3.1")


class DocType(BaseModel):
    id: str
    title: str
    keywords: list[str] = Field(default_factory=list)
    fields: list[DocField]

    def required_fields(self) -> list[DocField]:
        return [f for f in self.fields if f.required]


class Settings(BaseModel):
    ocr_engine: str = "tesseract"
    ocr_lang: str = "rus"
    preprocess: dict = Field(default_factory=dict)
    regulation: dict = Field(default_factory=dict)
    confidence: dict = Field(default_factory=dict)
    detectors: dict = Field(default_factory=dict)
    cache_size: int = 32


@lru_cache
def load_settings() -> Settings:
    data = yaml.safe_load((CONFIGS / "settings.yaml").read_text(encoding="utf-8")) or {}
    s = Settings(**data)
    s.ocr_engine = os.environ.get("OCR_ENGINE", s.ocr_engine)
    return s


@lru_cache
def load_doc_types() -> dict[str, DocType]:
    """Новый тип документа = новый YAML в configs/doc_types, код не трогаем."""
    out: dict[str, DocType] = {}
    for p in sorted((CONFIGS / "doc_types").glob("*.yaml")):
        dt = DocType(**yaml.safe_load(p.read_text(encoding="utf-8")))
        out[dt.id] = dt
    return out
