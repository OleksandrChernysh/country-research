#!/usr/bin/env python3
"""Tax residency and net-balance calculator reading .env + tax_calc_model from countries/*.json."""

import glob
import json
import os
from typing import Dict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, ".env")
COUNTRIES_DIR = os.path.join(ROOT, "countries")


def load_env(path: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not os.path.exists(path):
        return env
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def calculate_country(model: Dict, env: Dict[str, str]) -> Dict:
    net_after_ua = float(env.get("NET_AFTER_UA_EUR") or 1500.0)
    tax_base_eur = float(env.get("TAX_BASE_EUR") or 1500.0)

    local_soc = float(model.get("soc_fixed", 0.0)) + float(model.get("soc_rate", 0.0)) * tax_base_eur
    pit_base = tax_base_eur * float(model.get("pit_base_scale", 1.0)) - float(model.get("pit_threshold", 0.0))
    if model.get("pit_deduct_soc"):
        pit_base -= local_soc
    local_pit = max(0.0, pit_base) * float(model.get("pit_rate", 0.0)) * float(model.get("pit_mult", 1.0))

    local_tax_total = local_pit + local_soc
    eff_pct = (local_tax_total / tax_base_eur) * 100.0 if tax_base_eur else 0.0

    fixed_costs = (
        float(env.get("PERSONAL_THERAPY_EUR") or 0.0)
        + float(env.get("PERSONAL_MEDS_EUR") or 0.0)
        + float(env.get("FAMILY_SUPPORT_UA_EUR") or 0.0)
    )
    living_total = float(model["rent_eur"]) + float(model["living_other_eur"]) + fixed_costs

    return {
        "name": model["label"],
        "tax_free_months": model["tax_free_months"],
        "local_tax_total": local_tax_total,
        "eff_pct": eff_pct,
        "living_total": living_total,
        "net_first_period": net_after_ua - living_total,
        "net_after_residency": net_after_ua - local_tax_total - living_total,
    }


def main():
    env = load_env(ENV_PATH)
    print("| Country | Tax-free (mo) | Living+Fixed (EUR) | Net 0% tax (EUR) | Local Tax+Soc (EUR) | Eff % | Net after Res (EUR) |")
    print("|---|---:|---:|---:|---:|---:|---:|")

    for path in sorted(glob.glob(os.path.join(COUNTRIES_DIR, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        model = data.get("tax_calc_model")
        if not model:
            continue
        r = calculate_country(model, env)
        print(
            f"| {r['name']} | {r['tax_free_months']} | {r['living_total']:.0f} | "
            f"{r['net_first_period']:+.0f} | {r['local_tax_total']:.2f} | "
            f"{r['eff_pct']:.1f}% | {r['net_after_residency']:+.2f} |"
        )


if __name__ == "__main__":
    main()
