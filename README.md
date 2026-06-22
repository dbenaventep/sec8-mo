# Section 8 Payment Standards — Rent by ZIP (2025 vs 2026)

A tiny static page to look up the **Housing Choice Voucher (Section 8) Payment
Standards** by ZIP code and compare the maximum rent per number of bedrooms
between **2025** and **2026**.

Enter a ZIP code and you get, per bedroom size, the 2026 rent (large), the 2025
rent (small), and a green ▲ / red ▼ triangle with the change in dollars and
percent.

## Live page

Hosted with GitHub Pages from this repo's root: open `index.html`.
Deep links work too, e.g. `…/index.html#63074`.

## Files

| File | What it is |
|------|------------|
| `index.html` | The whole app (HTML + CSS + vanilla JS, no build step). |
| `data.js` / `data.json` | Generated rent tables keyed by ZIP code. |
| `parse.py` | Extracts the data from the source PDFs into `data.*`. |
| `2025-Payment-Standards.pdf`, `2026-Payment-Standards.pdf` | Source documents. |

## Regenerating the data

If the source PDFs change, re-run the parser:

```bash
pip install pypdf
python3 parse.py
```

This rewrites `data.json` and `data.js`.

## Enabling GitHub Pages

1. Push this folder to a public GitHub repository.
2. **Settings → Pages → Build and deployment → Source: Deploy from a branch.**
3. Pick the `main` branch and the `/ (root)` folder, then save.

## Notes

- Some ZIP codes appear in only one year (e.g. `63005`, `63131` are 2026-only).
  In those cases the missing year shows `N/A` and the change shows `—`.
- The page works offline / from `file://` because the data is bundled in
  `data.js`; no server or network request is needed.
