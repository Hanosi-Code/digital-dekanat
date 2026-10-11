from pathlib import Path

from dekanat.core.config import ROOT, load_doc_types
from dekanat.core.kb.parser import parse_regulation

RULES = parse_regulation((ROOT / "data/regulations/rules.md").read_text(encoding="utf-8"))
IDS = {c.id for c in RULES}


def test_all_30_clauses_parsed():
    assert len(RULES) == 30
    assert {"1.3", "3.1", "3.4", "4.3", "5.3", "6.3"} <= IDS


def test_clause_text_not_truncated():
    c = {c.id: c for c in RULES}
    assert "сотрудник деканата" in c["1.3"].text
    assert "печать вуза" in c["3.3"].text.lower()


def test_config_refs_exist_in_rules():
    for dt in load_doc_types().values():
        for f in dt.fields:
            for r in f.regulation_refs:
                assert r in IDS, f"{dt.id}.{f.id}: пункта {r} нет в Положении"
