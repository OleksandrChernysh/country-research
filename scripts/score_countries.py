#!/usr/bin/env python3
"""Deterministic partial country scoring from .env + countries/*.json (zero hardcoded countries)."""

import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, ".env")
COUNTRIES_DIR = os.path.join(ROOT, "countries")

MEDS_TIER_PTS = {
    "fast": 10,
    "carrier": 6,
    "standard": 2,
    "blocked": -20,
}


def load_env(path: str) -> dict[str, str]:
    env = {}
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


def score_country(c: dict, env: dict[str, str]) -> dict:
    low_budget_only = env.get("LOW_BUDGET_ONLY", "true").lower() == "true"
    avoid_mil_rule = env.get("AVOID_MILITARY_RULE_COUNTRIES", "true").lower() == "true"
    prefer_non_eu = env.get("PREFER_NON_EU", "false").lower() == "true"
    meds_req = env.get("MEDICINE_DELIVERY_REQUIRED", "true").lower() == "true"
    priority_climate = env.get("PRIORITY_CLIMATE", "warm_low_heating")
    main_religion_pref = env.get("MAIN_RELIGION", "any").strip().lower()

    ineligible_reasons: list[str] = []

    # 1. Budget (max 30)
    is_lb = bool(c.get("low_budget_country", False))
    if low_budget_only and not is_lb:
        ineligible_reasons.append("not_low_budget")
    budget_pts = 30 if is_lb else (0 if low_budget_only else 10)

    # 2. Climate & heating efficiency (max 25)
    heat_m = c.get("weather", {}).get("heating_months_below_15c", 6)
    if priority_climate == "warm_low_heating":
        if heat_m == 0:
            climate_pts = 25
        elif heat_m <= 3:
            climate_pts = 20
        elif heat_m <= 5:
            climate_pts = 15
        elif heat_m <= 7:
            climate_pts = 8
        else:
            climate_pts = 2
    else:
        climate_pts = 15

    # 3. Military + Visa / >183d Stay Legality (max 20)
    requires_dereg = bool(c.get("requires_military_deregistration", False))
    visa_ua = c.get("visa_ua", {})
    visa_days = visa_ua.get("visa_free_days") or 0
    req_type = visa_ua.get("requirement_type")
    is_eu = bool(c.get("is_eu", False))
    has_tp = bool(c.get("has_temporary_protection", False))
    has_low_nomad = bool(c.get("has_low_threshold_nomad_visa", False))

    if avoid_mil_rule and requires_dereg:
        legal_pts = -50
        ineligible_reasons.append("requires_military_deregistration")
    elif visa_days >= 360 or has_low_nomad:
        legal_pts = 20
    elif has_tp and not is_eu:
        legal_pts = 14
    elif has_tp and is_eu:
        legal_pts = 10
    elif req_type == "unknown":
        legal_pts = 0
    elif req_type in ("e_visa", "visa_on_arrival"):
        legal_pts = -5
    elif visa_days <= 30 or not has_tp:
        legal_pts = -15
    else:
        legal_pts = 0

    if prefer_non_eu and not is_eu and not (avoid_mil_rule and requires_dereg):
        legal_pts = min(20, legal_pts + 5)

    # 4. UA FOP tax load >183d (max 15) — prefer structured tax_calc_model over text heuristics
    model = c.get("tax_calc_model")
    if model:
        tax_base = float(env.get("TAX_BASE_EUR") or 1500.0)
        net_after_ua = float(env.get("NET_AFTER_UA_EUR") or 1500.0)
        local_soc = float(model.get("soc_fixed", 0.0)) + float(model.get("soc_rate", 0.0)) * tax_base
        soc_thr = model.get("soc_threshold_eur")
        if soc_thr is not None and tax_base >= float(soc_thr):
            local_soc += float(model.get("soc_fixed_above_threshold", 0.0))
        pit_base = tax_base * float(model.get("pit_base_scale", 1.0)) - float(model.get("pit_threshold", 0.0))
        if model.get("pit_deduct_soc"):
            pit_base -= local_soc
        local_pit = max(0.0, pit_base) * float(model.get("pit_rate", 0.0)) * float(model.get("pit_mult", 1.0))
        local_tax = local_pit + local_soc
        eff_pct = (local_tax / tax_base) * 100.0 if tax_base else 0.0
        horizon_months = max(1, int(float(env.get("TAX_HORIZON_MONTHS") or 36)))
        tax_free_months = max(0, min(horizon_months, int(model.get("tax_free_months", 0))))
        horizon_eff_pct = eff_pct * ((horizon_months - tax_free_months) / horizon_months)
        if horizon_eff_pct <= 5.0:
            tax_pts = 15
        elif horizon_eff_pct <= 15.0:
            tax_pts = 10
        elif horizon_eff_pct <= 22.0:
            tax_pts = 7
        else:
            tax_pts = 2

        fixed_costs = (
            float(env.get("PERSONAL_THERAPY_EUR") or 0.0)
            + float(env.get("PERSONAL_MEDS_EUR") or 0.0)
            + float(env.get("FAMILY_SUPPORT_UA_EUR") or 0.0)
        )
        living_total = float(model["rent_eur"]) + float(model["living_other_eur"]) + fixed_costs
        if net_after_ua - local_tax - living_total < 0:
            tax_pts -= 15
            ineligible_reasons.append("negative_net_after_residency")
    else:
        tax_text = (c.get("ua_fop_and_local_taxes") or "").lower()
        if "0 €" in tax_text and ("1st year" in tax_text or "year 1" in tax_text or "1-й рік" in tax_text or "0–31" in tax_text):
            tax_pts = 15
        elif any(x in tax_text for x in ("10.88%", "10%", "111–159", "20% pit", "114–143")):
            tax_pts = 10
        elif any(x in tax_text for x in ("200–230", "15% pit")):
            tax_pts = 7
        else:
            tax_pts = 2

    # 5. Medicine delivery from origin (max 10, penalty -20 if blocked)
    if not meds_req:
        meds_pts = 10
    else:
        tier = c.get("medicine_delivery_tier", "standard")
        meds_pts = MEDS_TIER_PTS.get(tier, 2)

    # 6. Main religion filter (0 when "any" or matched, -20 + ineligible when mismatched/excluded)
    religion_pts = 0
    country_religion = (c.get("main_religion") or "").strip().lower()
    if main_religion_pref and main_religion_pref != "any":
        if main_religion_pref.startswith("exclude:"):
            excluded = {x.strip() for x in main_religion_pref[8:].split(",") if x.strip()}
            if country_religion in excluded:
                religion_pts = -20
                ineligible_reasons.append("religion_excluded")
        else:
            allowed = {x.strip() for x in main_religion_pref.split(",") if x.strip()}
            if country_religion not in allowed:
                religion_pts = -20
                ineligible_reasons.append("religion_mismatch")

    total = budget_pts + climate_pts + legal_pts + tax_pts + meds_pts + religion_pts
    return {
        "eligible": len(ineligible_reasons) == 0,
        "ineligible_reasons": ineligible_reasons,
        "auto_score": total,
        "breakdown": {
            "budget": budget_pts,
            "climate": climate_pts,
            "legal": legal_pts,
            "tax": tax_pts,
            "medicine": meds_pts,
            "religion": religion_pts,
        },
    }


def main():
    env = load_env(ENV_PATH)
    files = sorted(glob.glob(os.path.join(COUNTRIES_DIR, "*.json")))
    scored = []
    for path in files:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        res = score_country(data, env)
        scored.append({
            "code": data["code"],
            "name": data["name"],
            "eligible": res["eligible"],
            "ineligible_reasons": res["ineligible_reasons"],
            "auto_score": res["auto_score"],
            "score_breakdown": res["breakdown"],
        })

    scored.sort(key=lambda x: (not x["eligible"], -x["auto_score"], x["code"]))
    rankings = {}
    for idx, item in enumerate(scored, 1):
        item["auto_rank"] = idx
        rankings[item["code"]] = item

    out_dir = os.path.join(ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "rankings.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(rankings, fh, ensure_ascii=False, indent=2)

    print("Top 10 by script (auto_score -> output/rankings.json):")
    for d in scored[:10]:
        print(f"  #{d['auto_rank']:2d} {d['code']} ({d['name']}): {d['auto_score']:3d} pts | {d['score_breakdown']}")


if __name__ == "__main__":
    main()
