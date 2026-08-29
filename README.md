# Barcode Generator Pro (EAN-13)

A desktop Windows application for generating EAN-13 barcode stickers with:
- Company name, product code, manufacturing date, expiry date, mobile number
- **Sheet printer mode**: A4 — 40/24/80/12 stickers per sheet, or fully custom
- **Label printer mode**: direct label printers (Zebra, TSC, Xprinter, Godex, Rongta)
  with 7 preset label sizes + custom size — one label per print
- Bulk CSV import
- History (SQLite)
- Bilingual UI (English + Urdu)

## Quick Build (on a Windows PC)

1. Install Python 3.10+ from https://python.org — check **Add Python to PATH**
2. Install Inno Setup 6 from https://jrsoftware.org/isdl.php
3. Open Command Prompt in this folder and run:
   ```
   build.bat
   ```
4. The installer will be created at `dist\BarcodeGeneratorPro_Setup.exe`

## Run as Developer (no install)

```
pip install -r requirements.txt
python main.py
```

## Automatic Build via GitHub Actions

This repo includes a workflow at `.github/workflows/build.yml` that:
- Runs on every push to `main` / `master`
- Runs on every tag push matching `v*` (e.g. `v1.0.0`)
- Can be triggered manually from the Actions tab

The workflow produces two artifacts (downloadable from the Actions run page):
- `BarcodeGeneratorPro-EXE` — standalone .exe
- `BarcodeGeneratorPro-Installer` — Windows installer .exe

When triggered by a `v*` tag, it also creates a GitHub Release with both files attached.

See `README.txt` for full Urdu + English user manual.
