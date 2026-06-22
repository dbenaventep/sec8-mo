#!/usr/bin/env python3
"""Extrae los Payment Standards (Section 8) desde los PDFs y genera data.json.

Estructura de salida:
{
  "bedrooms": ["Efficiency", "1 Bedroom", ...],
  "years": {
    "2025": { "<zip>": [eff, 1br, 2br, 3br, 4br, 5br], ... },
    "2026": { ... }
  }
}
Cada valor de renta es un entero (USD).
"""
import json
import re
import sys

import pypdf

BEDROOMS = ["Efficiency", "1 Bedroom", "2 Bedroom", "3 Bedroom", "4 Bedroom", "5 Bedroom"]

# Un "Area" = 6 montos en dólares seguidos de una lista de ZIP codes (5 dígitos)
# hasta el siguiente "Area" o el fin del documento.
MONEY = r"\$\s*([\d,]+)"
AREA_RE = re.compile(
    r"Area\s+\d+.*?ZIP Codes\s*"          # encabezado del área
    + r"\s*".join([MONEY] * 6)            # 6 montos
    + r"\s*((?:\d{5}\s*)+)",              # uno o más zip codes
    re.DOTALL,
)


def parse_pdf(path):
    reader = pypdf.PdfReader(path)
    text = " ".join(page.extract_text() for page in reader.pages)
    result = {}
    for m in AREA_RE.finditer(text):
        rents = [int(m.group(i).replace(",", "")) for i in range(1, 7)]
        zips = re.findall(r"\d{5}", m.group(7))
        for z in zips:
            result[z] = rents
    return result


def main():
    data = {
        "bedrooms": BEDROOMS,
        "years": {
            "2025": parse_pdf("2025-Payment-Standards.pdf"),
            "2026": parse_pdf("2026-Payment-Standards.pdf"),
        },
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


if __name__ == "__main__":
    main()
