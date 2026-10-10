"""Метрики на открытых данных. Запускайте после КАЖДОГО изменения OCR/правил.

Формат эталонов (data/eval/gold.json) — ПРЕДПОЛОЖЕНИЕ, подгоните под данные организаторов:
[{"id": "...", "file": "doc1.jpg", "doc_type": "study_certificate",
  "fields": {"student_name": "Иванов Иван Иванович", ...},
  "question": "...", "verdict": "missing", "sources": ["3.4"]}]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dekanat.core.pipeline import Pipeline  # noqa: E402


def norm(v) -> str:
    return " ".join(str(v).lower().split()) if v is not None else ""


def main(gold_path: str = "data/eval/gold.json") -> None:
    gold_file = Path(gold_path)
    items = json.loads(gold_file.read_text(encoding="utf-8"))
    pipe = Pipeline()
    f_ok = f_all = v_ok = s_ok = 0
    times = []
    for it in items:
        path = gold_file.parent / it["file"]
        t = time.perf_counter()
        resp = pipe.run(path.read_bytes(), path.name, it["question"], it.get("doc_type"))
        times.append(time.perf_counter() - t)
        for fid, expected in it.get("fields", {}).items():
            got = resp.card.fields.get(fid)
            f_all += 1
            f_ok += int(got is not None and norm(got.value) == norm(expected))
        v_ok += int(resp.answer.verdict == it.get("verdict"))
        gold_src = set(it.get("sources", []))
        got_src = {s.ref for s in resp.answer.sources if s.type == "regulation"}
        s_ok += int(gold_src == got_src)
    n = max(len(items), 1)
    print(f"Документов:      {len(items)}")
    print(f"Точность полей:  {f_ok}/{f_all} = {f_ok / max(f_all, 1):.1%}")
    print(f"Точность вердикта: {v_ok / n:.1%}")
    print(f"Точность ссылок:   {s_ok / n:.1%}")
    print(f"Среднее время:   {sum(times) / n:.1f} c")


if __name__ == "__main__":
    main(*sys.argv[1:2])
