"""Положение (txt) -> JSON с пунктами. Нужен для проверки разбора глазами:
python scripts/build_kb.py data/regulations/polozhenie.txt"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dekanat.core.kb.parser import parse_regulation  # noqa: E402

src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/regulations/polozhenie.txt")
clauses = parse_regulation(src.read_text(encoding="utf-8"))
out = src.with_suffix(".clauses.json")
out.write_text(json.dumps([c.__dict__ for c in clauses], ensure_ascii=False, indent=2),
               encoding="utf-8")
print(f"Пунктов: {len(clauses)} -> {out}")
