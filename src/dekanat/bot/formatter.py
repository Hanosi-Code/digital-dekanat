from __future__ import annotations

from html import escape

ICONS = {"ok": "✅", "missing": "⚠️", "no_data": "❓"}


def format_card(card: dict, doc_type: dict) -> str:
    labels = {f["id"]: f["label"] for f in doc_type["fields"]}
    rows = [f"<b>{escape(doc_type['title'])}</b>"]
    for fid, fr in card["fields"].items():
        if fr["status"] != "found":
            val = "не найдено"
        elif fr["value"] is True:
            val = "есть"
        elif fr["value"] is False:
            val = "нет"
        else:
            val = escape(str(fr["value"]))
        rows.append(f"• {escape(labels.get(fid, fid))}: {val}")
    return "\n".join(rows)


def format_answer(resp: dict) -> str:
    a = resp["answer"]
    parts = [f"{ICONS.get(a['verdict'], '')} {escape(a['answer'])}"]
    srcs = [s for s in a.get("sources", []) if s["type"] == "regulation"]
    if srcs:
        parts.append("\n<i>Источники:</i> " + ", ".join(f"п. {escape(s['ref'])}" for s in srcs))
    return "\n".join(parts)
