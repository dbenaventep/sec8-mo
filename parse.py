#!/usr/bin/env python3
"""Extrae los Payment Standards (Section 8) desde los PDFs y genera data.json.

Cubre DOS autoridades distintas:
  - St. Louis Housing Authority (SLHA): ciudad + condado, areas con ZIPs.
    Adopta el SAFMR de HUD ~1:1, así que enrich.py le proyecta un 2027.
  - St. Charles County PHA (administrado por NECAC): tabla city/ZIP. NO sigue
    el SAFMR 1:1 (~116% en 2026), por lo que NO se le proyecta 2027.

Estructura de salida:
{
  "bedrooms": [...],
  "years": { "2025": {zip: [eff,1br,..,5br]}, "2026": {...} },
  "zipMeta": { "<zip>": {"authority":..., "authorityShort":..., "adopts_safmr": bool, "city"?:...} }
}
Cada valor de renta es un entero (USD).
"""
import json
import re
import sys

import pypdf

BEDROOMS = ["Efficiency", "1 Bedroom", "2 Bedroom", "3 Bedroom", "4 Bedroom", "5 Bedroom"]

SLHA = {"authority": "City of St. Louis Housing Authority (SLHA)",
        "authorityShort": "SLHA", "adopts_safmr": True}
SCC = {"authority": "St. Charles County PHA (NECAC)",
       "authorityShort": "St. Charles County PHA", "adopts_safmr": False}

# --- SLHA: un "Area" = 6 montos en dólares + una lista de ZIPs (5 dígitos) ---
MONEY = r"\$\s*([\d,]+)"
AREA_RE = re.compile(
    r"Area\s+\d+.*?ZIP Codes\s*"
    + r"\s*".join([MONEY] * 6)
    + r"\s*((?:\d{5}\s*)+)",
    re.DOTALL,
)

# --- St. Charles (NECAC): filas "CITY/ZIP 0BR 1BR 2BR 3BR 4BR 5BR 6BR" ---
SCC_ROW_RE = re.compile(
    r"([A-Z.&'\- ]+?)\s*/\s*(\d{5})\s+((?:\d{3,4}\s+){6}\d{3,4})"
)


def parse_slha(path):
    reader = pypdf.PdfReader(path)
    text = " ".join(page.extract_text() for page in reader.pages)
    result = {}
    for m in AREA_RE.finditer(text):
        rents = [int(m.group(i).replace(",", "")) for i in range(1, 7)]
        for z in re.findall(r"\d{5}", m.group(7)):
            result[z] = rents
    return result


def parse_st_charles(path):
    """Devuelve (rents_by_zip, city_by_zip). Mapea 0BR..5BR (ignora 6BR)."""
    reader = pypdf.PdfReader(path)
    text = " ".join(page.extract_text() for page in reader.pages)
    rents, cities = {}, {}
    for m in SCC_ROW_RE.finditer(text):
        city = m.group(1).strip().title()
        z = m.group(2)
        nums = [int(x) for x in m.group(3).split()]   # 7 valores: 0BR..6BR
        rents[z] = nums[:6]                            # Eff..5BR
        cities[z] = city
    return rents, cities


def main():
    y2025 = parse_slha("2025-Payment-Standards.pdf")
    y2026 = parse_slha("2026-Payment-Standards.pdf")

    zip_meta = {z: dict(SLHA) for z in set(y2025) | set(y2026)}

    stc_2026, stc_cities = parse_st_charles("2026-St-Charles-Payment-Standards.pdf")
    for z, rents in stc_2026.items():
        if z in y2026:                       # no debería ocurrir (jurisdicciones distintas)
            print(f"WARN: {z} en ambas autoridades", file=sys.stderr)
        y2026[z] = rents
        zip_meta[z] = {**SCC, "city": stc_cities.get(z)}

    data = {
        "bedrooms": BEDROOMS,
        "years": {"2025": y2025, "2026": y2026},
        "zipMeta": zip_meta,
    }
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)

    # data.js permite abrir index.html directamente (file://) sin servidor.
    with open("data.js", "w") as f:
        f.write("const PAYMENT_DATA = ")
        json.dump(data, f, indent=2)
        f.write(";\n")

    for year, table in data["years"].items():
        print(f"{year}: {len(table)} ZIP codes", file=sys.stderr)
    print(f"St. Charles (NECAC) 2026: {len(stc_2026)} ZIPs added", file=sys.stderr)


if __name__ == "__main__":
    main()
