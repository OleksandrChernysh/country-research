#!/usr/bin/env python3
"""Fetch passport visa-free limits from ilyankou/passport-index-dataset using ISO codes in countries/*.json."""

from datetime import date
import csv
import glob
import io
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, ".env")
COUNTRIES_DIR = os.path.join(ROOT, "countries")
DATASET_URL = "https://raw.githubusercontent.com/ilyankou/passport-index-dataset/master/passport-index-tidy-iso2.csv"


def classify_requirement(req: str) -> tuple[int | None, str]:
    if req.isdigit():
        return int(req), "visa_free"
    low = req.lower()
    if low == "e-visa":
        return None, "e_visa"
    if low == "visa on arrival":
        return None, "visa_on_arrival"
    if low == "visa required":
        return 0, "visa_required"
    return None, "unknown"


def load_origin_passport(path: str) -> str:
    if not os.path.exists(path):
        return "UA"
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("ORIGIN_PASSPORT="):
                return s.split("=", 1)[1].strip().strip('"').strip("'")
    return "UA"


def main():
    passport = load_origin_passport(ENV_PATH)
    with urllib.request.urlopen(DATASET_URL, timeout=20) as resp:
        text = resp.read().decode("utf-8")

    reqs = {}
    for row in csv.DictReader(io.StringIO(text)):
        if row["Passport"] == passport:
            reqs[row["Destination"]] = row["Requirement"].strip()

    files = sorted(glob.glob(os.path.join(COUNTRIES_DIR, "*.json")))
    for path in files:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        iso = data.get("iso_alpha2", data["code"])
        req = reqs.get(iso, "unknown")
        days, req_type = classify_requirement(req)
        data["visa_ua"] = {
            "requirement": req,
            "requirement_type": req_type,
            "visa_free_days": days,
            "fetched_at": date.today().isoformat(),
            "source": DATASET_URL,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    print(f"Updated visa_ua ({passport}) for {len(files)} countries from passport-index-dataset.")


if __name__ == "__main__":
    main()
