"""Пакетный прогон: документы + вопросы -> results.json (формат README v1.0).

Запуск (папка с файлами выдачи: documents.json, questions.json, изображения/PDF):
    python scripts/run_batch.py --documents data/closed/documents.json \
        --questions data/closed/questions.json --files-dir data/closed -o results.json

Формат documents.json в вашем окружении я не видел, поэтому поиск файла гибкий:
берётся document_id, document_type (или type) и первое строковое значение записи, похожее на
путь к .png/.jpg/.jpeg/.pdf. Предпочтение отдаётся PNG (--prefer pdf меняет на PDF).
Проверка формата и метрик: evaluate.py организаторов.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dekanat.core.export import export_document, export_results  # noqa: E402
from dekanat.core.pipeline import Pipeline  # noqa: E402

EXT = (".png", ".jpg", ".jpeg", ".pdf")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def iter_documents(data) -> list[dict]:
    if isinstance(data, dict):
        data = data.get("documents", data)
    if isinstance(data, dict):                      # {"open-001": {...}}
        return [{"document_id": k, **v} for k, v in data.items()]
    return list(data)


def find_files(doc: dict) -> list[str]:
    found: list[str] = []

    def walk(v):
        if isinstance(v, str) and v.lower().endswith(EXT):
            found.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(doc)
    return found


def resolve(doc: dict, files_dir: Path, prefer: str) -> Path:
    cands = find_files(doc)
    cands.sort(key=lambda c: (not c.lower().endswith("." + prefer.lower()), c))
    for c in cands:
        for base in (files_dir, files_dir.parent, Path(".")):
            p = base / c
            if p.exists():
                return p
    for ext in ([prefer] + [e.strip(".") for e in EXT if e.strip(".") != prefer]):
        p = files_dir / f"{doc['document_id']}.{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"Не найден файл для {doc['document_id']} (искал в {files_dir})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--documents", type=Path, required=True)
    ap.add_argument("--questions", type=Path, required=True)
    ap.add_argument("--files-dir", type=Path, default=None)
    ap.add_argument("--prefer", default="png", choices=["png", "pdf", "jpg"])
    ap.add_argument("-o", "--out", type=Path, default=Path("results.json"))
    args = ap.parse_args()

    files_dir = args.files_dir or args.documents.parent
    docs = iter_documents(load_json(args.documents))
    by_doc: dict[str, list[dict]] = {}
    for q in load_json(args.questions):
        by_doc.setdefault(q["document_id"], []).append(q)

    pipe = Pipeline()
    out_docs, errors = [], 0
    for doc in docs:
        did = doc["document_id"]
        dtype = doc.get("document_type") or doc.get("type")
        if dtype not in pipe.doc_types:
            raise SystemExit(f"{did}: неизвестный тип {dtype!r}")
        try:
            path = resolve(doc, files_dir, args.prefer)
            card, validation, dt, _, _ = pipe.analyze_document(path.read_bytes(), path.name, dtype)
        except Exception as e:  # noqa: BLE001  один плохой файл не должен ронять весь прогон
            errors += 1
            print(f"[!] {did}: {e}", file=sys.stderr)
            from dekanat.core.schemas import Card
            from dekanat.core.reason import validate
            dt = pipe.doc_types[dtype]
            card = Card(doc_type=dtype)                       # всё «не найдено» / false
            validation = validate(card, dt)
        answers = [pipe.answer(card, validation, dt, q["question"], q["question_id"])
                   for q in by_doc.get(did, [])]
        out_docs.append(export_document(did, card, dt, validation, answers))
        print(f"{did}: {validation.status}, пропусков: {len(validation.missing_fields)}")

    args.out.write_text(json.dumps(export_results(out_docs), ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"Готово: документов {len(out_docs)}, ошибок {errors} -> {args.out}")


if __name__ == "__main__":
    main()
