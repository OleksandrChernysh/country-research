#!/usr/bin/env python3
"""Validate countries/*.json structure, tax_calc_model fields, and check for accidental personal contacts."""

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COUNTRIES_DIR = os.path.join(ROOT, "countries")

REQUIRED_KEYS = ("code", "name", "low_budget_country", "weather", "visa_ua")
TAX_MODEL_KEYS = ("label", "rent_eur", "living_other_eur", "pit_rate", "tax_free_months")
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"\+\d[\d\s\-()]{6,}")


def validate_file(path: str) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a single country JSON file."""
    errors: list[str] = []
    warnings: list[str] = []
    name = os.path.basename(path)

    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [f"{name}: invalid JSON ({exc})"], []

    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"{name}: missing required key '{key}'")

    model = data.get("tax_calc_model")
    if model is not None:
        if not isinstance(model, dict):
            errors.append(f"{name}: tax_calc_model must be an object")
        else:
            for key in TAX_MODEL_KEYS:
                if key not in model:
                    errors.append(f"{name}: tax_calc_model missing '{key}'")

    if EMAIL_RE.findall(raw):
        warnings.append(f"{name}: contains email-like string(s)")
    if PHONE_RE.findall(raw):
        errors.append(f"{name}: contains phone number(s): {PHONE_RE.findall(raw)}")

    return errors, warnings


def main() -> int:
    files = sorted(glob.glob(os.path.join(COUNTRIES_DIR, "*.json")))
    all_errors: list[str] = []
    all_warnings: list[str] = []

    for path in files:
        errs, warns = validate_file(path)
        all_errors.extend(errs)
        all_warnings.extend(warns)

    for w in all_warnings:
        print(f"WARN: {w}")
    for e in all_errors:
        print(f"ERROR: {e}")

    print(f"Validated {len(files)} country JSON files: {len(all_errors)} error(s), {len(all_warnings)} warning(s).")
    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
