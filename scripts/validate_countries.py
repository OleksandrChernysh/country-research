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

    if "low_budget_country" in data and not isinstance(data["low_budget_country"], bool):
        errors.append(f"{name}: low_budget_country must be a boolean")
    if "weather" in data and not isinstance(data["weather"], dict):
        errors.append(f"{name}: weather must be an object")
    if "visa_ua" in data and not isinstance(data["visa_ua"], dict):
        errors.append(f"{name}: visa_ua must be an object")

    model = data.get("tax_calc_model")
    if model is not None:
        if not isinstance(model, dict):
            errors.append(f"{name}: tax_calc_model must be an object")
        else:
            for key in TAX_MODEL_KEYS:
                if key not in model:
                    errors.append(f"{name}: tax_calc_model missing '{key}'")
            for num_key in ("rent_eur", "living_other_eur", "tax_free_months"):
                val = model.get(num_key)
                if val is not None and (isinstance(val, bool) or not isinstance(val, (int, float)) or val < 0):
                    errors.append(f"{name}: tax_calc_model.{num_key} must be a non-negative number")
            pit_rate = model.get("pit_rate")
            if pit_rate is not None and (isinstance(pit_rate, bool) or not isinstance(pit_rate, (int, float)) or not (0 <= pit_rate <= 1)):
                errors.append(f"{name}: tax_calc_model.pit_rate must be between 0 and 1")

    if EMAIL_RE.findall(raw):
        warnings.append(f"{name}: contains email-like string(s)")
    phone_matches = PHONE_RE.findall(raw)
    if phone_matches:
        errors.append(f"{name}: contains {len(phone_matches)} phone-like string(s)")

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
