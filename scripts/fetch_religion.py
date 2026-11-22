#!/usr/bin/env python3
"""Fetch main_religion for all countries/*.json from Wikipedia (Pew Research 2020 Religious Landscape)."""

import glob
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COUNTRIES_DIR = os.path.join(ROOT, "countries")
WIKI_API_URL = (
    "https://en.wikipedia.org/w/api.php"
    "?action=parse&page=Religions_by_country&prop=wikitext&format=json"
)

CATEGORIES = [
    "christianity",
    "islam",
    "unaffiliated",
    "hinduism",
    "buddhism",
    "other",
    "judaism",
]

COUNTRY_ALIASES = {
    "Czechia": "Czech Republic",
    "USA": "United States",
    "Bosnia and Herzegovina": "Bosnia-Herzegovina",
}


def parse_count(raw: str) -> int:
    s = raw.strip().replace(",", "")
    if s in ("<10K", "<10,000", "—", "-", ""):
        return 0
    return int(s)


def fetch_pew_religions() -> dict[str, tuple[str, float]]:
    """Return {country_name: (main_religion, share_pct)} from Pew 2020 table."""
    req = urllib.request.Request(WIKI_API_URL, headers={"User-Agent": "country-research/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    wikitext = payload["parse"]["wikitext"]["*"]
    section = wikitext.split("== 2020 Pew Research World Religious Landscape ==")[1]
    rows = section.split("\n|-\n")

    results: dict[str, tuple[str, float]] = {}
    for row in rows:
        lines = [line.strip() for line in row.splitlines() if line.strip().startswith("|")]
        if len(lines) < 9:
            continue
        cname = re.sub(r"\{\{[^}]+\}\}", "", lines[0][1:]).strip()
        cname = re.sub(r"\[\[([^|\]]+\|)?([^\]]+)\]\]", r"\2", cname).strip()
        counts = [parse_count(line[1:]) for line in lines[1:8]]
        total = parse_count(lines[8][1:])
        if total <= 0:
            continue
        best_idx = max(range(len(counts)), key=lambda i: counts[i])
        pct = round((counts[best_idx] / total) * 100.0, 1)
        results[cname] = (CATEGORIES[best_idx], pct)
    return results


def main() -> None:
    pew_data = fetch_pew_religions()
    files = sorted(glob.glob(os.path.join(COUNTRIES_DIR, "*.json")))
    updated = 0
    for path in files:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        name = data["name"]
        lookup = name if name in pew_data else COUNTRY_ALIASES.get(name, name)
        if lookup not in pew_data:
            raise KeyError(f"Missing Pew religion data for {data['code']} ({name})")
        main_rel, pct = pew_data[lookup]
        data["main_religion"] = main_rel
        data["main_religion_pct"] = pct
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        updated += 1
        print(f"  {data['code']} ({name}): {main_rel} ({pct}%)")
    print(f"Updated main_religion in {updated} country JSON files.")


if __name__ == "__main__":
    main()
