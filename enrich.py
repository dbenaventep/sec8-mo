#!/usr/bin/env python3
"""Enriquece data.json con contexto por ZIP: Census ACS + HUD Small Area FMR.

Requiere un archivo .env (gitignoreado) con:
    CENSUS_API_KEY=...
    HUD_API_TOKEN=...

Las credenciales se usan SOLO en build time; nunca se publican en el sitio.

Uso:  python3 enrich.py     (corre después de parse.py)
"""
import json
import os
import sys
import urllib.parse
import urllib.request

ACS_YEAR = 2024          # último vintage ACS 5-year disponible (2020-2024)
FMR_YEAR = 2026
STL_METRO = "METRO41180M41180"   # St. Louis, MO-IL HUD Metro FMR Area

# Variable ACS -> nombre corto
ACS_VARS = {
    "B01003_001E": "population",
    "B19013_001E": "median_income",
    "B25064_001E": "median_gross_rent",
    "B25003_001E": "occupied_units",
    "B25003_003E": "renter_units",
    "B17001_001E": "poverty_universe",
    "B17001_002E": "poverty_count",
    "B08013_001E": "agg_commute_minutes",
    "B08303_001E": "commute_workers",
    "B25070_001E": "rent_burden_universe",
    "B25070_007E": "rb_30_35",
    "B25070_008E": "rb_35_40",
    "B25070_009E": "rb_40_50",
    "B25070_010E": "rb_50_plus",
}


def load_env(path=".env"):
    env = {}
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    for k in ("CENSUS_API_KEY", "HUD_API_TOKEN"):
        env.setdefault(k, os.environ.get(k, ""))
    return env


def get_json(url, headers=None, timeout=120):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def num(v):
    """ACS usa negativos grandes (-666666666) como 'sin dato'."""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return None if n < 0 else n


def fetch_acs(zips, key):
    """Una sola llamada para todos los ZCTA; filtramos localmente.

    Es mucho más rápido y evita el throttling que gatillan 60 requests
    individuales contra la API del Census.
    """
    cols = list(ACS_VARS)
    url = (
        f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5?get="
        + ",".join(cols)
        + "&for="
        + urllib.parse.quote("zip code tabulation area:*")
        + f"&key={key}"
    )
    rows = get_json(url)
    header = rows[0]
    zi = header.index("zip code tabulation area")
    idx = {c: header.index(c) for c in cols}

    out = {}
    for row in rows[1:]:
        z = row[zi]
        if z not in zips:
            continue
        raw = {name: num(row[idx[var]]) for var, name in ACS_VARS.items()}

        rec = {
            "population": raw["population"],
            "median_income": raw["median_income"],
            "median_gross_rent": raw["median_gross_rent"],
        }

        if raw["occupied_units"] and raw["renter_units"] is not None:
            rec["renter_pct"] = round(raw["renter_units"] / raw["occupied_units"] * 100, 1)
        if raw["poverty_universe"] and raw["poverty_count"] is not None:
            rec["poverty_pct"] = round(raw["poverty_count"] / raw["poverty_universe"] * 100, 1)
        if raw["commute_workers"] and raw["agg_commute_minutes"]:
            rec["mean_commute_min"] = round(raw["agg_commute_minutes"] / raw["commute_workers"], 1)
        if raw["rent_burden_universe"]:
            burdened = sum(
                raw[k] or 0 for k in ("rb_30_35", "rb_35_40", "rb_40_50", "rb_50_plus")
            )
            rec["rent_burdened_pct"] = round(burdened / raw["rent_burden_universe"] * 100, 1)

        out[z] = rec
    return out


def fetch_safmr(token):
    """Small Area Fair Market Rents por ZIP (benchmark federal)."""
    data = get_json(
        f"https://www.huduser.gov/hudapi/public/fmr/data/{STL_METRO}?year={FMR_YEAR}",
        headers={"Authorization": f"Bearer {token}"},
    )["data"]
    # FMR llega solo hasta 4 dormitorios; el 5º no existe en la fuente.
    keys = ["Efficiency", "One-Bedroom", "Two-Bedroom", "Three-Bedroom", "Four-Bedroom"]
    return {
        r["zip_code"]: [r.get(k) for k in keys]
        for r in data["basicdata"]
        if r["zip_code"] != "MSA level"
    }


def main():
    env = load_env()
    if not env["CENSUS_API_KEY"] or not env["HUD_API_TOKEN"]:
        sys.exit("Faltan CENSUS_API_KEY / HUD_API_TOKEN (revisa .env)")

    data = json.load(open("data.json"))
    zips = set(data["years"]["2025"]) | set(data["years"]["2026"])

    print(f"ACS {ACS_YEAR} 5-year: descargando todos los ZCTA...", file=sys.stderr)
    acs = fetch_acs(zips, env["CENSUS_API_KEY"])
    print(f"  -> {len(acs)}/{len(zips)} ZIPs con datos ACS", file=sys.stderr)

    print(f"HUD SAFMR {FMR_YEAR}...", file=sys.stderr)
    safmr = fetch_safmr(env["HUD_API_TOKEN"])
    matched = {z: safmr[z] for z in zips if z in safmr}
    print(f"  -> {len(matched)}/{len(zips)} ZIPs con SAFMR", file=sys.stderr)

    data["acs"] = {"year": ACS_YEAR, "label": f"ACS {ACS_YEAR} 5-year", "byZip": acs}
    data["safmr"] = {"year": FMR_YEAR, "label": f"HUD Small Area FMR {FMR_YEAR}", "byZip": matched}

    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)
    with open("data.js", "w") as f:
        f.write("const PAYMENT_DATA = ")
        json.dump(data, f, indent=2)
        f.write(";\n")
    print("data.json / data.js actualizados", file=sys.stderr)


if __name__ == "__main__":
    main()
