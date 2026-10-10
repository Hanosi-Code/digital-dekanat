# Онлайн-деканат — цифровой секретарь (Telegram-бот)

Бот читает фото/скан/PDF студенческого документа, заполняет карточку полей и отвечает на вопрос
**со ссылкой на пункт Положения**. Если ответа нет в документе и Положении, честно об этом говорит.

## Архитектура

```
Telegram ──► bot (aiogram) ──HTTP──► api (FastAPI) ──► core.pipeline
                                          ▲                │
                      scripts/run_batch.py┘   ingest → preprocess(OpenCV) → OCR
                                              → extract (поля, печать/подпись)
                                              → kb.retrieve (Положение) → reason → answer
```

- `src/dekanat/core` — вся логика, не зависит от Telegram и FastAPI.
- `src/dekanat/api` — HTTP-обёртка (`/analyze`, `/doc-types`, `/health`).
- `src/dekanat/bot` — тонкий клиент Telegram.
- `configs/doc_types/*.yaml` — типы документов и поля. **Новый тип = новый YAML, без кода.**
- `configs/settings.yaml` — пороги и флаги предобработки.
- `data/regulations/polozhenie.txt` — Положение (пока пример, замените на файл организаторов).
- `scripts/` — `run_batch.py` (results.json), `evaluate.py` (метрики), `build_kb.py` (проверка разбора).

## Быстрый старт

```bash
cp .env.example .env          # впишите BOT_TOKEN от @BotFather
docker compose up --build
```

API: http://localhost:8000/docs

Локально без Docker (нужны tesseract и tesseract-ocr-rus):
```bash
pip install -r requirements-dev.txt
export PYTHONPATH=src
pytest
uvicorn dekanat.api.main:app --reload
python -m dekanat.bot.main     # в другом терминале, нужен BOT_TOKEN и API_URL
```

## Что нужно доделать (TODO)

1. Положить настоящее Положение в `data/regulations/polozhenie.txt`, поправить `kb/parser.py` под его формат.
2. Заменить плейсхолдеры `regulation_refs` в `configs/doc_types/*.yaml` реальными пунктами.
3. Подогнать якоря и регулярки под открытые документы организаторов.
4. Подогнать `scripts/run_batch.py` и `scripts/evaluate.py` под формат из README к датасету.
5. Сравнить OCR-движки (Tesseract / EasyOCR / Paddle) на открытых данных, подобрать пороги.
6. Бонусы: автоопределение типа (`extract/doctype.py` — базовая версия есть), подсветка поля на снимке (bbox уже хранятся), устойчивость к плохим снимкам.

## Используемые инструменты (для защиты)

Python 3.11, FastAPI, aiogram 3, OpenCV, Tesseract OCR (+ опционально EasyOCR / PaddleOCR), PyMuPDF,
собственный BM25 для поиска по Положению. Внешние LLM API не используются.
