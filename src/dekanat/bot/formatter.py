from __future__ import annotations

from html import escape

from ..core.schemas import NOT_FOUND

VALIDATION_ICON = {"document_ok": "✅", "missing_fields": "⚠️"}


def format_card(card: dict, doc_type: dict) -> str:
    labels = {f["id"]: f["label"] for f in doc_type["fields"]}
    rows = [f"<b>{escape(doc_type['title'])}</b>"]
    for fid, fr in card["fields"].items():
        if fr["status"] != "found":
            val = NOT_FOUND if not isinstance(fr.get("value"), bool) else "нет"
        elif fr["value"] is True:
            val = "есть"
        elif fr["value"] is False:
            val = "нет"
        else:
            val = escape(str(fr["value"]))
        rows.append(f"• {escape(labels.get(fid, fid))}: {val}")
    return "\n".join(rows)


def _source(src: str, labels: dict[str, str]) -> str:
    kind, ref = src.split(":", 1)
    return f"п. {ref} Положения" if kind == "rule" else f"поле «{labels.get(ref, ref)}»"


def format_answer(resp: dict, doc_type: dict) -> str:
    a, v = resp["answer"], resp["validation"]
    labels = {f["id"]: f["label"] for f in doc_type["fields"]}
    if a["intent"] == "completeness":
        icon = VALIDATION_ICON.get(v["status"], "")
    elif a["answerable"]:
        icon = "📄" if a["intent"] == "field" else "ℹ️"
    else:
        icon = "❓"
    parts = [f"{icon} {escape(a['answer'])}"]
    if a["sources"]:
        parts.append("\n<i>Источники:</i> " + escape("; ".join(_source(s, labels) for s in a["sources"])))
        quotes = [f"п. {k}: {t}" for k, t in resp.get("rule_texts", {}).items()
                  if f"rule:{k}" in a["sources"]]
        if quotes and a["intent"] == "completeness" and v["status"] == "missing_fields":
            parts.append("\n".join("• " + escape(q) for q in quotes[:3]))
    return "\n".join(parts)
