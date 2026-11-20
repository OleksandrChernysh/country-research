#!/usr/bin/env python3
"""Fetch multi-year climate normals from NASA POWER API using coordinates stored in countries/*.json."""

import concurrent.futures
from datetime import date
import glob
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COUNTRIES_DIR = os.path.join(ROOT, "countries")
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def fetch_city_weather(path: str) -> tuple[str, dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    w = data.get("weather", {})
    city = w.get("reference_city", data["name"])
    coords = w.get("coordinates", {})
    lat, lon = coords["lat"], coords["lon"]

    nasa_url = (
        "https://power.larc.nasa.gov/api/temporal/climatology/point"
        f"?parameters=T2M,T2M_MAX,T2M_MIN,RH2M&community=RE&latitude={lat}&longitude={lon}&format=JSON"
    )
    with urllib.request.urlopen(nasa_url, timeout=20) as resp:
        raw = json.loads(resp.read().decode())

    params = raw["properties"]["parameter"]
    t_mean = params["T2M"]
    t_max = params["T2M_MAX"]
    t_min = params["T2M_MIN"]
    rh = params["RH2M"]

    def avg(keys, src):
        return round(sum(src[k] for k in keys) / len(keys), 1)

    heating_months = sum(1 for m in MONTHS if t_mean[m] < 15.0)
    weather = {
        "reference_city": city,
        "coordinates": {"lat": lat, "lon": lon},
        "annual_mean_c": round(t_mean["ANN"], 1),
        "winter_djf_c": {"mean": avg(["DEC", "JAN", "FEB"], t_mean), "min": avg(["DEC", "JAN", "FEB"], t_min), "max": avg(["DEC", "JAN", "FEB"], t_max)},
        "spring_mam_c": {"mean": avg(["MAR", "APR", "MAY"], t_mean), "min": avg(["MAR", "APR", "MAY"], t_min), "max": avg(["MAR", "APR", "MAY"], t_max)},
        "summer_jja_c": {"mean": avg(["JUN", "JUL", "AUG"], t_mean), "min": avg(["JUN", "JUL", "AUG"], t_min), "max": avg(["JUN", "JUL", "AUG"], t_max)},
        "autumn_son_c": {"mean": avg(["SEP", "OCT", "NOV"], t_mean), "min": avg(["SEP", "OCT", "NOV"], t_min), "max": avg(["SEP", "OCT", "NOV"], t_max)},
        "humidity_annual_pct": round(rh["ANN"], 1),
        "heating_months_below_15c": heating_months,
        "monthly_mean_c": {m.lower(): round(t_mean[m], 1) for m in MONTHS},
        "api_sources": {
            "nasa_power_climatology": nasa_url,
            "fetched_at": date.today().isoformat(),
        },
    }
    return path, weather


def main():
    files = sorted(glob.glob(os.path.join(COUNTRIES_DIR, "*.json")))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(fetch_city_weather, files))

    for path, weather in results:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["weather"] = weather
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    print(f"Updated weather data from NASA POWER API for {len(files)} countries.")


if __name__ == "__main__":
    main()
