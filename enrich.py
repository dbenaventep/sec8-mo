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
FMR_YEAR = 2026          # FMR que respalda los standards 2026 oficiales
PROJECT_YEAR = 2027      # próximo año a proyectar desde el SAFMR federal (None lo apaga)
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


def fetch_safmr(token, year=FMR_YEAR):
    """Small Area Fair Market Rents por ZIP (benchmark federal) para un año."""
    data = get_json(
        f"https://www.huduser.gov/hudapi/public/fmr/data/{STL_METRO}?year={year}",
        headers={"Authorization": f"Bearer {token}"},
    )["data"]
    # FMR llega solo hasta 4 dormitorios; el 5º no existe en la fuente.
    keys = ["Efficiency", "One-Bedroom", "Two-Bedroom", "Three-Bedroom", "Four-Bedroom"]
    return {
        r["zip_code"]: [r.get(k) for k in keys]
        for r in data["basicdata"]
        if r["zip_code"] != "MSA level"
    }


def projected_year(safmr):
    """Payment standard provisional a partir del SAFMR federal de ese año.

    La autoridad local adopta el SAFMR casi 1:1 (verificado: 2026 calzó al
    0-2%). El SAFMR trae 5 tamaños (hasta 4BR); el 5BR se deriva con la propia
    fórmula de HUD — 5BR = round(1.15 x 4BR) — que reproduce exactamente los
    valores 5BR de los PDFs oficiales 2025 y 2026 en los 115 registros.

    Es una PROYECCIÓN, no el schedule oficial; se marca como provisional.
    """
    out = {}
    for z, vals in safmr.items():
        if None in vals:
            continue
        four = vals[4]
        out[z] = list(vals) + [round(four * 1.15)]  # 6 valores: Eff..5BR
    return out


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
    safmr = fetch_safmr(env["HUD_API_TOKEN"], FMR_YEAR)
    matched = {z: safmr[z] for z in zips if z in safmr}
    print(f"  -> {len(matched)}/{len(zips)} ZIPs con SAFMR", file=sys.stderr)

    # Proyección provisional del próximo año desde el SAFMR federal FY<n>,
    # ya publicado por HUD aunque la autoridad local no haya sacado su PDF.
    proj = {}
    if PROJECT_YEAR:
        print(f"HUD SAFMR {PROJECT_YEAR} (provisional)...", file=sys.stderr)
        try:
            proj_safmr = fetch_safmr(env["HUD_API_TOKEN"], PROJECT_YEAR)
            proj = {z: v for z, v in projected_year(proj_safmr).items() if z in zips}
            print(f"  -> {len(proj)}/{len(zips)} ZIPs proyectados", file=sys.stderr)
        except Exception as e:  # el año aún no existe en HUD -> se omite
            print(f"  -> sin datos {PROJECT_YEAR}: {e}", file=sys.stderr)

    data["acs"] = {"year": ACS_YEAR, "label": f"ACS {ACS_YEAR} 5-year", "byZip": acs}
    data["safmr"] = {"year": FMR_YEAR, "label": f"HUD Small Area FMR {FMR_YEAR}", "byZip": matched}

    if proj:
        data["years"][str(PROJECT_YEAR)] = proj
        data.setdefault("provisional", {})[str(PROJECT_YEAR)] = {
            "label": f"{PROJECT_YEAR} (projected)",
            "source": f"HUD Small Area FMR FY{PROJECT_YEAR}",
            "note": (
                f"Provisional: the city/county had not published official "
                f"{PROJECT_YEAR} payment standards as of the build date. These "
                f"are HUD's FY{PROJECT_YEAR} Small Area FMRs, which the authority "
                f"has historically adopted within ~0-2%. The 5-bedroom figure is "
                f"derived as 1.15x the 4-bedroom, per HUD's own formula."
            ),
        }

    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)
    with open("data.js", "w") as f:
        f.write("const PAYMENT_DATA = ")
        json.dump(data, f, indent=2)
        f.write(";\n")
    print("data.json / data.js actualizados", file=sys.stderr)


if __name__ == "__main__":
    main()
