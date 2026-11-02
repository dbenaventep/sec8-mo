# Section 8 Payment Standards — Rent by ZIP (2025 vs 2026)

A tiny static page to look up the **Housing Choice Voucher (Section 8) Payment
Standards** by ZIP code and compare the maximum rent per number of bedrooms
between **2025** and **2026**.

## Two tools

- **Look up** — enter a single ZIP code and get, per bedroom size, the latest
  year large, the earlier years as history, and a green ▲ / red ▼ triangle with
  the change in dollars and percent. Plus a **voucher power** meter (how the
  standard compares to the typical rent actually charged in that ZIP) and a
  **neighborhood profile** (income, rental supply, poverty, rent burden,
  commute).
- **Compare ZIPs** — add several ZIP codes and see them side by side in one
  table: rows are bedroom sizes, one column per ZIP. A ★ marks the highest 2026
  rent in each row.

## Live page

Hosted with GitHub Pages from this repo's root: open `index.html`.

Deep links work for both tools:

| Link | Opens |
|------|-------|
| `…/index.html#63074` | Look up for ZIP 63074 |
| `…/index.html#compare=63116,63106,63131` | Comparison of those three ZIPs |

## Files

| File | What it is |
|------|------------|
| `index.html` | The whole app (HTML + CSS + vanilla JS, no build step). |
| `data.js` / `data.json` | Generated data: rents by ZIP + ACS and FMR context. |
| `parse.py` | Extracts the payment standards from the source PDFs. |
| `enrich.py` | Adds Census ACS and HUD SAFMR context, plus the projected 2027. |
| `build_api.py` | Generates the static JSON API under `api/`. |
| `api/` | Generated static JSON API (one file per ZIP + indexes). |
| `2025/2026-Payment-Standards.pdf` | SLHA (St. Louis) source documents. |
| `2026-St-Charles-Payment-Standards.pdf` | St. Charles County (NECAC) source. |

## JSON API (static)

GitHub Pages is static, so there is no server — instead the build emits one JSON
file per ZIP. GitHub Pages sends `Access-Control-Allow-Origin: *`, so you can
`fetch` these from anywhere.

| Endpoint | Returns |
|----------|---------|
| `api/zip/<zip>.json` | One ZIP: payment standards (2025/2026/2027) + neighborhood |
| `api/index.json` | Metadata, available years, full ZIP list, URL template |
| `api/all.json` | Every ZIP in a single file |

```bash
curl https://dbenaventep.github.io/sec8-mo/api/zip/63116.json
```

```js
const r = await fetch('https://dbenaventep.github.io/sec8-mo/api/zip/63116.json');
const { payment_standards } = await r.json();
console.log(payment_standards['2027']['2 Bedroom']); // 1310
```

Payment standards are keyed by bedroom label; a year is omitted for a ZIP that
has no data that year. `2027` is provisional — see `provisional_years` in the
payload.

## Data sources

| Source | Used for | Vintage |
|--------|----------|---------|
| SLHA Payment Standards PDFs | St. Louis city/county rent by ZIP | 2025, 2026 (official) |
| [St. Charles County PHA / NECAC PDF](https://necac.org/images/pdfs/housing/sccpha-payment-standards-2026.pdf) | St. Charles County rent by ZIP | 2026 (official, eff. Jul 1) |
| [HUD Small Area FMR](https://www.huduser.gov/portal/dataset/fmr-api.html) | **Projected 2027** (SLHA only) + federal benchmark | FY2026, FY2027 |
| [Census ACS 5-year](https://www.census.gov/data/developers/data-sets/acs-5year.html) | Income, typical rent, rental supply, poverty, rent burden, commute | 2024 (covers 2020–2024) |

### Two authorities

The app covers two separate housing authorities, tagged per ZIP in `zipMeta`:

- **St. Louis city/county — SLHA.** Adopts HUD's Small Area FMR ~1:1 (the 2026
  standards matched FY2026 SAFMR on all ZIPs), so a provisional **2027** is
  projected from FY2027 SAFMR.
- **St. Charles County — NECAC.** Sets standards differently (2026 ran ~116% of
  SAFMR) on a July 1 cycle, so **no 2027 is projected** for it — those ZIPs show
  2026 only. 9 ZIPs: St. Charles, St. Peters, O'Fallon, Wentzville, Lake St.
  Louis, Foristell.

### The projected 2027 column

As of the latest build, neither the city nor the county had published official
2027 payment standards (those schedules take effect January 1 and are typically
released in Nov–Dec). HUD's **FY2027 Small Area FMRs** are already published,
though, and the local authority has historically adopted them within ~0–2% (the
2026 standards matched the 2026 SAFMR on all 60 ZIPs). So the app shows a
**provisional 2027** column, clearly badged, built from the FY2027 SAFMRs. The
5-bedroom figure is derived as `round(1.15 × 4-bedroom)` — HUD's own formula,
which reproduces the official 5BR values exactly across every 2025/2026 row.
When the real schedule drops, replace the PDFs and re-run the scripts.

Caveats worth knowing:

- ACS is a **5-year average** centered around 2022, so it trails the 2026
  payment standards. It is good for structural context (who lives there, how
  much housing is rented), not for current asking rents.
- The Census reports on **ZCTAs**, which approximate but do not exactly match
  USPS ZIP codes.
- Federal FMR only goes up to 4 bedrooms; there is no 5-bedroom figure.

## Regenerating the data

If the source PDFs change, re-run the parser:

```bash
pip install pypdf
python3 parse.py
```

To also refresh the ACS / HUD context you need two free API credentials
([Census](https://api.census.gov/data/key_signup.html),
[HUD](https://www.huduser.gov/portal/dataset/fmr-api.html)) in a local `.env`
file, which is gitignored and never shipped to the site:

```bash
cat > .env <<'EOF'
CENSUS_API_KEY=your_key
HUD_API_TOKEN=your_token
EOF
python3 enrich.py
```

The full build order is:

```bash
python3 parse.py && python3 enrich.py && python3 build_api.py
```

`parse.py` / `enrich.py` rewrite `data.json` and `data.js`; `build_api.py`
regenerates `api/`. **Always re-run `build_api.py` after any data change** and
commit the `api/` folder, or the JSON API will serve stale figures.

## Enabling GitHub Pages

1. Push this folder to a public GitHub repository.
2. **Settings → Pages → Build and deployment → Source: Deploy from a branch.**
3. Pick the `main` branch and the `/ (root)` folder, then save.

## Notes

- Some ZIP codes appear in only one year (e.g. `63005`, `63131` are 2026-only).
  In those cases the missing year shows `N/A` and the change shows `—`.
- The page works offline / from `file://` because the data is bundled in
  `data.js`; no server or network request is needed.
