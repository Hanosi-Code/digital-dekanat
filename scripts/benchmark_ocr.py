"""Сравнение OCR-движков и предобработки на открытых документах (день 2).

Для каждой комбинации «условие снимка × движок × предобработка» прогоняет документы,
собирает results.json в формате README и считает метрики ТЕМ ЖЕ evaluate.py организаторов.

Примеры:
  python scripts/benchmark_ocr.py --docs-dir data/open --engines tesseract
  python scripts/benchmark_ocr.py --docs-dir data/open --engines tesseract,easyocr \
      --conditions clean,rot15,photo --limit 5 --out outputs/bench

--docs-dir: папка, где лежит documents/open-XXX.png (относительные пути берутся из documents.json).
Документы без PNG пропускаются, эталон фильтруется до найденных документов.
"""
import argparse
import csv
import importlib.util
import json
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dekanat.bench.degrade import CONDITIONS, apply  # noqa: E402
from dekanat.core.config import load_settings  # noqa: E402
from dekanat.core.export import export_document, export_results  # noqa: E402
from dekanat.core.extract.fields import extract_card  # noqa: E402
from dekanat.core.ocr import get_engine, group_lines  # noqa: E402
from dekanat.core.pipeline import Pipeline  # noqa: E402
from dekanat.core.preprocess import preprocess  # noqa: E402
from dekanat.core.reason import validate  # noqa: E402


def load_org_evaluator():
    """evaluate.py организаторов; грузим по пути, чтобы не конфликтовать с пакетом evaluate (HF)."""
    spec = importlib.util.spec_from_file_location("org_evaluate", ROOT / "scripts" / "evaluate.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_docs(docs_dir: Path, eval_dir: Path, limit: int | None):
    meta = json.loads((eval_dir / "documents.json").read_text(encoding="utf-8"))
    questions = json.loads((eval_dir / "questions.json").read_text(encoding="utf-8"))
    by_doc: dict[str, list[dict]] = {}
    for q in questions:
        by_doc.setdefault(q["document_id"], []).append(q)
    docs = []
    for d in meta:
        path = docs_dir / d["image"]
        if path.exists():
            docs.append({**d, "path": path, "questions": by_doc.get(d["document_id"], [])})
    if limit:
        # равномерно по типам: по limit документов каждого типа
        seen: dict[str, int] = {}
        picked = []
        for d in docs:
            seen[d["document_type"]] = seen.get(d["document_type"], 0) + 1
            if seen[d["document_type"]] <= limit:
                picked.append(d)
        docs = picked
    return docs


def analyze(img, dtype, engine, pre_on: bool, settings, pipe):
    """Один документ: предобработка -> OCR -> поля -> проверка. Возвращает (card, validation, сек_ocr)."""
    pre_cfg = dict(settings.preprocess)
    pre_cfg["enabled"] = pre_on
    im = preprocess(img, pre_cfg)
    t = time.perf_counter()
    words = engine.read(im)
    ocr_sec = time.perf_counter() - t
    lines = group_lines(words)
    card = extract_card(pipe.doc_types[dtype], lines, im, settings)
    return card, validate(card, pipe.doc_types[dtype]), ocr_sec


def run_cell(docs, cond, engine, pre_on, settings, pipe, org_eval, reference):
    out_docs, ocr_times, t0 = [], [], time.perf_counter()
    for d in docs:
        img = cv2.imread(str(d["path"]))
        img = apply(cond, img, d["document_id"])
        dt = pipe.doc_types[d["document_type"]]
        card, val, ocr_sec = analyze(img, d["document_type"], engine, pre_on, settings, pipe)
        ocr_times.append(ocr_sec)
        answers = [pipe.answer(card, val, dt, q["question"], q["question_id"]) for q in d["questions"]]
        out_docs.append(export_document(d["document_id"], card, dt, val, answers))
    total = time.perf_counter() - t0
    report = org_eval.evaluate(reference, export_results(out_docs))
    return {
        "condition": cond, "engine": engine.name, "preprocess": "on" if pre_on else "off",
        "documents": len(docs),
        "field_acc": report["field_accuracy_macro"],
        "validation_em": report["validation_exact_match"],
        "question_em": report["question_exact_match"],
        "ocr_sec_per_doc": round(sum(ocr_times) / len(docs), 2),
        "total_sec_per_doc": round(total / len(docs), 2),
        "errors": report["errors"][:6],
    }


def to_markdown(rows):
    head = ["Условие", "Движок", "Предобр.", "Поля", "Проверка", "Вопросы", "OCR, с/док", "Всего, с/док"]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * len(head)) + "|"]
    for r in rows:
        lines.append(f"| {r['condition']} | {r['engine']} | {r['preprocess']} | {r['field_acc']:.3f} | "
                     f"{r['validation_em']:.3f} | {r['question_em']:.3f} | {r['ocr_sec_per_doc']} | "
                     f"{r['total_sec_per_doc']} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs-dir", type=Path, default=ROOT / "data" / "open")
    ap.add_argument("--eval-dir", type=Path, default=ROOT / "data" / "eval")
    ap.add_argument("--engines", default="tesseract")
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--preprocess", default="off,on", help="off,on | on | off")
    ap.add_argument("--limit", type=int, default=None, help="документов КАЖДОГО типа (для быстрой проверки)")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs" / "bench")
    args = ap.parse_args()

    settings, pipe, org_eval = load_settings(), Pipeline(), load_org_evaluator()
    docs = load_docs(args.docs_dir, args.eval_dir, args.limit)
    if not docs:
        sys.exit(f"Не найдено ни одного PNG в {args.docs_dir} (ожидается documents/open-XXX.png)")
    ids = {d["document_id"] for d in docs}
    reference = json.loads((args.eval_dir / "reference_results.json").read_text(encoding="utf-8"))
    reference["documents"] = [d for d in reference["documents"] if d["document_id"] in ids]
    print(f"Документов: {len(docs)}; условия: {args.conditions}; движки: {args.engines}", flush=True)

    engines = []
    for name in args.engines.split(","):
        try:
            engines.append(get_engine(name.strip(), settings.ocr_lang))
        except Exception as e:  # noqa: BLE001
            print(f"[!] движок {name} недоступен: {e}", file=sys.stderr)
    pre_modes = [m.strip() == "on" for m in args.preprocess.split(",")]

    rows = []
    for cond in args.conditions.split(","):
        for eng in engines:
            for pre_on in pre_modes:
                row = run_cell(docs, cond.strip(), eng, pre_on, settings, pipe, org_eval, reference)
                rows.append(row)
                print(f"{cond:>7} {eng.name:>9} pre={row['preprocess']:<3} поля={row['field_acc']:.3f} "
                      f"проверка={row['validation_em']:.3f} вопросы={row['question_em']:.3f} "
                      f"ocr={row['ocr_sec_per_doc']}с", flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "bench_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.out / "bench_table.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[k for k in rows[0] if k != "errors"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    (args.out / "bench_table.md").write_text(to_markdown(rows) + "\n", encoding="utf-8")
    print(f"\nГотово -> {args.out}/bench_table.md, bench_table.csv, bench_results.json")


if __name__ == "__main__":
    main()
