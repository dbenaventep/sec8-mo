#!/usr/bin/env python3
"""Genera una "static API" (JSON por ZIP) servible desde GitHub Pages.

Como Pages es estático no hay servidor; en su lugar escribimos un archivo
por ZIP en api/zip/<zip>.json, más índices. GitHub Pages responde con
Access-Control-Allow-Origin: *, así que se consume por fetch desde cualquier
origen.

Rutas generadas (relativas a la raíz del sitio):
    api/index.json         -> metadatos, fuentes, lista de ZIPs, plantilla de URL
    api/zip/<zip>.json      -> payment standards + barrio para un ZIP
    api/all.json            -> todos los ZIPs en un solo archivo

Uso:  python3 build_api.py   (después de parse.py + enrich.py)
"""
import datetime
import json
import os
import shutil

SITE = "https://dbenaventep.github.io/sec8-mo"
OUT = "api"
TODAY = datetime.date.today().isoformat()

DISCLAIMER = (
    "Unofficial. Payment standards for 2025/2026 are transcribed from the "
    "published Payment Standards PDFs; 2027 is provisional (projected from HUD "
    "FY2027 Small Area FMRs). Verify against the housing authority before relying "
    "on these figures."
)


def labeled(bedrooms, values):
    """[880, 920, ...] -> {'Efficiency': 880, '1 Bedroom': 920, ...} (skips None)."""
    return {bed: v for bed, v in zip(bedrooms, values) if v is not None}


def zip_payload(zip_code, data):
    bedrooms = data["bedrooms"]
    years = {
        y: labeled(bedrooms, table[zip_code])
        for y, table in data["years"].items()
        if zip_code in table
    }
    acs = data.get("acs", {}).get("byZip", {}).get(zip_code)
    meta = data.get("zipMeta", {}).get(zip_code, {})

    return {
        "zip": zip_code,
        "city": meta.get("city"),
        "authority": meta.get("authority"),
        "bedrooms": bedrooms,
        "payment_standards": years,
        "provisional_years": {
            y: meta for y, meta in data.get("provisional", {}).items() if y in years
        },
        "neighborhood": acs,
        "sources": {
            "payment_standards_2025_2026": "Local housing authority Payment Standards PDFs",
            "payment_standards_2027": data.get("provisional", {}).get("2027", {}).get("source"),
            "neighborhood": data.get("acs", {}).get("label"),
        },
        "generated": TODAY,
        "disclaimer": DISCLAIMER,
    }


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def main():
    data = json.load(open("data.json"))
    zips = sorted(set().union(*(set(t) for t in data["years"].values())))

    # Carpeta limpia para no dejar ZIPs viejos si la lista cambia.
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)

    payloads = {z: zip_payload(z, data) for z in zips}
    for z, payload in payloads.items():
        write_json(f"{OUT}/zip/{z}.json", payload)

    write_json(f"{OUT}/all.json", {
        "generated": TODAY,
        "count": len(zips),
        "zips": payloads,
    })

    write_json(f"{OUT}/index.json", {
        "name": "St. Louis Section 8 Payment Standards — unofficial static API",
        "generated": TODAY,
        "years": sorted(data["years"]),
        "provisional_years": sorted(data.get("provisional", {})),
        "bedrooms": data["bedrooms"],
        "count": len(zips),
        "zips": zips,
        "endpoints": {
            "by_zip": f"{SITE}/{OUT}/zip/{{zip}}.json",
            "all": f"{SITE}/{OUT}/all.json",
            "index": f"{SITE}/{OUT}/index.json",
        },
        "cors": "Access-Control-Allow-Origin: * (served by GitHub Pages)",
        "disclaimer": DISCLAIMER,
    })

    print(f"API generada: {len(zips)} ZIPs en {OUT}/zip/ + index.json + all.json")


if __name__ == "__main__":
    main()
