"""Проверка разбора Положения: python scripts/check_kb.py [data/regulations/rules.md]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dekanat.core.kb.parser import parse_regulation  # noqa: E402

src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/regulations/rules.md")
clauses = parse_regulation(src.read_text(encoding="utf-8"))
for c in clauses:
    print(f"{c.id:>4}  {c.text[:90]}")
print(f"\nПунктов: {len(clauses)}")
