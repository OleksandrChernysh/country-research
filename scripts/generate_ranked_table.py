#!/usr/bin/env python3
"""Generate RANKED_COUNTRIES.md from countries/*.json + rankings.json + ai_rankings.json."""

import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "countries")
OUT_DIR = os.path.join(ROOT, "output")
RANKINGS_PATH = os.path.join(OUT_DIR, "rankings.json")
AI_RANKINGS_PATH = os.path.join(OUT_DIR, "ai_rankings.json")
OUT = os.path.join(OUT_DIR, "RANKED_COUNTRIES.md")


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def row_str(c: dict, pos: int) -> str:
    w = c.get("weather", {})
    ann = w.get("annual_mean_c", "—")
    win = w.get("winter_djf_c", {}).get("mean", "—")
    lb = "🟢" if c.get("low_budget_country") else "—"
    v = c.get("visa_ua", {}).get("requirement", "—")
    b = c.get("score_breakdown", {})
    brk = f"{b.get('budget',0)}/{b.get('climate',0)}/{b.get('legal',0)}/{b.get('tax',0)}/{b.get('medicine',0)}"
    elig = "✅" if c.get("eligible", True) else f"❌ ({', '.join(c.get('ineligible_reasons', [])) or 'ineligible'})"
    return (
        f"| {pos} | `{c['code']}` | [{c['name']}](../countries/{c['code']}.json) | "
        f"{elig} | **{c.get('auto_score', 0)}** (`{brk}`) | #{c.get('ai_rank', '—')} | "
        f"{lb} | `{v}` | {ann}° / {win}° |"
    )


def main():
    rankings = load_json(RANKINGS_PATH, {})
    ai_ranks = load_json(AI_RANKINGS_PATH, {})
    has_ai = bool(ai_ranks)
    countries = []
    for path in glob.glob(os.path.join(DIR, "*.json")):
        with open(path, encoding="utf-8") as fh:
            c = json.load(fh)
        code = c["code"]
        r = rankings.get(code, {})
        c["auto_rank"] = r.get("auto_rank", 999)
        c["auto_score"] = r.get("auto_score", 0)
        c["score_breakdown"] = r.get("score_breakdown", {})
        c["eligible"] = r.get("eligible", True)
        c["ineligible_reasons"] = r.get("ineligible_reasons", [])
        c["ai_rank"] = ai_ranks.get(code, "—") if has_ai else "—"
        countries.append(c)

    by_script = sorted(countries, key=lambda c: (c["auto_rank"], c["code"]))

    lines = ["# Country Rankings", ""]
    lines += [
        "## 1. Script Ranking (`score_countries.py`)",
        "",
        "| Script # | Code | Country | Eligible | Score (`B/C/L/T/M`) | AI # | Low Budget | Visa UA | Weather (Ann/Win) |",
        "|---:|:---:|---|---:|---:|---:|:---:|:---:|---:|",
    ]
    for c in by_script:
        lines.append(row_str(c, c["auto_rank"]))

    if has_ai:
        by_ai = sorted(countries, key=lambda c: (c["ai_rank"] if isinstance(c["ai_rank"], int) else 999, c["auto_rank"]))
        by_combined = sorted(
            countries,
            key=lambda c: (0.5 * c["auto_rank"] + 0.5 * (c["ai_rank"] if isinstance(c["ai_rank"], int) else 999), -c["auto_score"]),
        )
        lines += [
            "",
            "## 2. AI Ranking (`output/ai_rankings.json`)",
            "",
            "| AI # | Code | Country | Eligible | Script Score (`B/C/L/T/M`) | AI # | Low Budget | Visa UA | Weather (Ann/Win) |",
            "|---:|:---:|---|---:|---:|---:|:---:|:---:|---:|",
        ]
        for c in by_ai:
            lines.append(row_str(c, c["ai_rank"]))

        lines += [
            "",
            "## 3. Combined Final Table (50% Script + 50% AI)",
            "",
            "| Final # | Code | Country | Eligible | Script Score (`B/C/L/T/M`) | AI # | Low Budget | Visa UA | Weather (Ann/Win) |",
            "|---:|:---:|---|---:|---:|---:|:---:|:---:|---:|",
        ]
        for idx, c in enumerate(by_combined, 1):
            lines.append(row_str(c, idx))
    else:
        lines += ["", "> Note: `output/ai_rankings.json` not found — AI and Combined 50/50 tables omitted."]

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    table_count = 3 if has_ai else 1
    print(f"Generated {OUT} with {table_count} table(s) ({len(countries)} countries).")


if __name__ == "__main__":
    main()
