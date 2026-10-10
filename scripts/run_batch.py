"""Пакетный прогон закрытых документов -> results.json.

ВАЖНО: формат входа и выхода описан в README к набору данных организаторов.
Пока он неизвестен, здесь рабочая заглушка с предположением (manifest.json со списком
{"id", "file", "question", "doc_type"?}). Подгоните `load_items` и `to_result` под README.

Запуск: python scripts/run_batch.py data/closed/manifest.json -o results.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dekanat.core.pipeline import Pipeline  # noqa: E402


def load_items(manifest: Path) -> list[dict]:
    # TODO: подогнать под формат организаторов
    return json.loads(manifest.read_text(encoding="utf-8"))


def to_result(item: dict, resp) -> dict:
    # TODO: подогнать ключи под формат results.json из README
    return {
        "id": item["id"],
        "doc_type": resp.card.doc_type,
        "fields": {k: (v.value if v.found else None) for k, v in resp.card.fields.items()},
        "verdict": resp.answer.verdict,
        "answer": resp.answer.answer,
        "sources": [s.ref for s in resp.answer.sources],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("results.json"))
    args = ap.parse_args()

    pipe = Pipeline()
    base = args.manifest.parent
    results = []
    for item in load_items(args.manifest):
        path = base / item["file"]
        try:
            resp = pipe.run(path.read_bytes(), path.name, item["question"], item.get("doc_type"))
            results.append(to_result(item, resp))
        except Exception as e:  # noqa: BLE001  один плохой файл не должен ронять весь прогон
            print(f"[!] {item.get('id')}: {e}", file=sys.stderr)
            results.append({"id": item.get("id"), "error": str(e)})
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Готово: {len(results)} записей -> {args.out}")


if __name__ == "__main__":
    main()
