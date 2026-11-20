# Country Research & Relocation Scoring

A data-driven relocation research repository that separates **objective country facts** (`countries/*.json`), **personal constraints** (`.env`), and **generated rankings** (`output/`).

All scripts use Python 3 standard library only (`urllib`, `json`, `csv`, `concurrent.futures`) — no third-party dependencies required.

---

## Architecture

```text
country-research/
├── .env.example                  # Trilingual (EN/UK/RU) configuration template
├── .env                          # Your personal config (gitignored)
├── .gitignore                    # Ignores .env, output/, __pycache__/
├── countries/                    # 30 structured country JSON files (objective facts + API data)
│   ├── AL.json
│   ├── GE.json
│   └── ...
├── scripts/
│   ├── fetch_weather.py          # Pulls multi-year climate normals from NASA POWER API
│   ├── fetch_visa_limits.py      # Pulls passport visa-free limits from passport-index-dataset
│   ├── score_countries.py        # Deterministic country scoring (.env + countries/*.json -> output/rankings.json)
│   ├── generate_ranked_table.py  # Builds 3 tables (Script, AI, 50/50 Combined) -> output/RANKED_COUNTRIES.md
│   ├── tax_residency_calc.py     # Net-income & tax-residency calculator (.env + tax_calc_model)
│   ├── find_matches.py           # Matches countries by region/population with tech relocation jobs
│   └── fetch_data.py             # Queries REST Countries API for region population/language summary
└── output/                       # All generated/user-specific outputs (gitignored)
    ├── rankings.json             # Generated script scores
    ├── ai_rankings.json          # Optional manual/AI qualitative ranks {"AL": 1, ...}
    └── RANKED_COUNTRIES.md       # Generated 3-table comparison report
```

---

## Quick Start

```bash
# 1. Create your personal config
cp .env.example .env

# 2. Edit .env with your budget, tax mode, military status, and preferences

# 3. (Optional) Refresh live external API data
python3 scripts/fetch_weather.py
python3 scripts/fetch_visa_limits.py

# 4. Compute deterministic scores & generate RANKED_COUNTRIES.md
python3 scripts/score_countries.py
python3 scripts/generate_ranked_table.py

# 5. Run tax-residency & net-balance breakdown
python3 scripts/tax_residency_calc.py
```

---

## Scripts Reference

### 1. `scripts/fetch_weather.py`
Fetches multi-year monthly and annual climate normals from the keyless **NASA POWER Climatology API** (`power.larc.nasa.gov`) using each country's `weather.reference_city` and `weather.coordinates` (`lat`, `lon`) stored in `countries/*.json`.

- **Concurrency:** Uses `ThreadPoolExecutor(max_workers=8)` to fetch all 30 countries in parallel.
- **Computed fields written under `weather` in each `countries/*.json`:**
  - `annual_mean_c` — annual mean 2m air temperature (°C)
  - `winter_djf_c`, `spring_mam_c`, `summer_jja_c`, `autumn_son_c` — seasonal `{mean, min, max}` (°C)
  - `humidity_annual_pct` — annual mean relative humidity (`RH2M`, %)
  - `heating_months_below_15c` — count of months where monthly mean temperature `< 15.0°C` (used for heating cost estimation)
  - `monthly_mean_c` — `jan` through `dec` monthly averages (°C)
  - `api_sources` — exact reproducible URLs for `nasa_power_climatology` and `open_meteo_archive`

### 2. `scripts/fetch_visa_limits.py`
Fetches visa-free stay limits for a given origin passport from the open-source **`ilyankou/passport-index-dataset`** (`passport-index-tidy-iso2.csv` on GitHub).

- **Configuration:** Reads `ORIGIN_PASSPORT` from `.env` (defaults to `"UA"`).
- **Mapping:** Matches each country's `iso_alpha2` (falling back to `code`, e.g., `UK` → `GB`).
- **Fields written under `visa_ua` in each `countries/*.json`:**
  - `requirement` — raw dataset value (e.g., `"90"`, `"360"`, `"30"`, `"e-visa"`, `"visa required"`)
  - `visa_free_days` — integer days when numeric, `0` otherwise
  - `source` — dataset URL

### 3. `scripts/score_countries.py`
Computes a deterministic **Script Ranking** (`auto_score` & `auto_rank`) for all countries in `countries/*.json` based on `.env` constraints, writing results to `rankings.json` (without mutating `countries/*.json`).

**Scoring Breakdown (max 100 pts):**

| Dimension | Max Pts | Logic |
|---|---:|---|
| `budget` | `30` | `30` if `low_budget_country == true`; otherwise `0` (when `LOW_BUDGET_ONLY=true`) or `10` |
| `climate` | `25` | When `PRIORITY_CLIMATE="warm_low_heating"`: `0` heating months = `25`, `1–3` = `20`, `4–5` = `15`, `6–7` = `8`, `8+` = `2` |
| `legal` | `20` | `-50` if `AVOID_MILITARY_RULE_COUNTRIES=true` and `requires_military_deregistration=true`; `20` if `visa_free_days >= 360` or `has_low_threshold_nomad_visa`; `14` if non-EU + Temporary Protection; `10` if EU + Temporary Protection; `-15` if `visa_free_days <= 30` or no TP |
| `tax` | `15` | Evaluates `ua_fop_and_local_taxes` post-183d burden (`15` for 0%/low-flat, `10` for moderate flat, `7` for ~15–20% + fixed social, `2` for high progressive EU/Western taxes) |
| `medicine` | `10` | Reads `medicine_delivery_tier` when `MEDICINE_DELIVERY_REQUIRED=true`: `fast` = `10`, `carrier` = `6`, `standard` = `2`, `blocked` = `-20` |

### 4. `scripts/generate_ranked_table.py`
Generates `RANKED_COUNTRIES.md` containing three Markdown tables across all 30 countries:
1. **Table 1 — Script Ranking:** Sorted by `auto_rank` from `rankings.json`.
2. **Table 2 — AI Ranking:** Sorted by `ai_rank` from optional local `ai_rankings.json` (`{"CODE": rank_int}`).
3. **Table 3 — Combined Final Table (50% Script + 50% AI):** Sorted by `0.5 * auto_rank + 0.5 * ai_rank` (tie-broken by `-auto_score`).

### 5. `scripts/tax_residency_calc.py`
Models net monthly cashflow before and after 183-day tax residency for every country in `countries/*.json` that defines a `tax_calc_model` block.

- **Inputs from `.env`:**
  - `NET_AFTER_UA_EUR` — net income after Ukrainian taxes
  - `TAX_BASE_EUR` — taxable base for local PIT/social calculations
  - `PERSONAL_THERAPY_EUR`, `PERSONAL_MEDS_EUR`, `FAMILY_SUPPORT_UA_EUR` — fixed monthly recurring costs
- **Output:** Prints a Markdown table with tax-free months, total living + fixed costs, net during tax-free window, local tax + social amount, effective tax %, and net after residency.

### 6. `scripts/find_matches.py`
Queries the **REST Countries API** (`mledoze/countries`) and **Tech Jobs with Relocation** (`AndrewStetsenko/tech-jobs-with-relocation`) to find countries matching a target region and minimum population that have active relocation tech employers.

```bash
python3 scripts/find_matches.py Europe 5000000
```

### 7. `scripts/fetch_data.py`
Queries `restcountries.com/v3.1/region/{region}` and prints the top countries by population along with their official languages.

---

## Country JSON Schema (`countries/*.json`)

Key standardized fields across the 30 country files:
- `code`, `name`, `iso_alpha2` (when different from `code`)
- `low_budget_country` (`bool`), `is_eu` (`bool`), `has_temporary_protection` (`bool`), `has_low_threshold_nomad_visa` (`bool`)
- `requires_military_deregistration` (`bool`), `medicine_delivery_tier` (`"fast" | "carrier" | "standard" | "blocked"`)
- `work_strategy`, `it_market`, `ua_fop_and_local_taxes`, `climate`, `nature`, `english_level`, `housing_rent`, `citizenship`, `mortgage_expats`, `rent_to_buy`, `spiritual_teacher`
- `price_sources` (Numbeo links + mandatory fields), `housing_portals`, `protection_and_aid_2026`, `ua_fop_tax_budget_2026`, `fallback_budget`, `tax_calc_model`
- `weather` (populated by `fetch_weather.py`)
- `visa_ua` (populated by `fetch_visa_limits.py`)

---

## External Data Sources
- **Weather / Climate Normals:** [NASA POWER](https://power.larc.nasa.gov/) & [Open-Meteo](https://open-meteo.com/) (keyless)
- **Visa-Free Stay Limits:** [ilyankou/passport-index-dataset](https://github.com/ilyankou/passport-index-dataset) (keyless)
- **Cost of Living (Food, Utilities, Rent):** [Numbeo](https://www.numbeo.com/cost-of-living/)
- **Country Metadata:** [REST Countries](https://restcountries.com/) & [mledoze/countries](https://github.com/mledoze/countries)
