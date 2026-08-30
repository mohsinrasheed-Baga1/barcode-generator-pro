============================================================
  BARCODE GENERATOR PRO  (EAN-13)  —  v2.0.3
  بارکوڈ جنریٹر پرو
============================================================

نئے فیچرز (v2.0.3):
  ✔ setFullPage(True) — ★ CRITICAL FIX — اب Qt خود اپنے margins
    شامل نہیں کرتا، پورا label استعمال ہوتا ہے
  ✔ 1.5×1 انچ preset — آپ کے label کا exact سائز (38.1×25.4 mm)
  ✔ 6 inch-based presets شامل کیے:
    1.5×1, 2×1, 3×1, 3×2, 4×2, 4×6 inches
  ✔ Test Print button — Print Setup dialog میں 1 label test
    print کرنے کا button شامل
  ✔ Printer info display — selected printer کا actual page size
    دکھاتا ہے، match ہونے پر ✓، مختلف ہونے پر ✗ warning
  ✔ Diagnostic info in errors — printer name, page size, DPI
    سب error message میں دکھاتا ہے

پرانے فیچرز (v2.0.1):
  ✔ Drag bug fix — ہر عنصر کو مکمل drag کریں، جتنا چاہیں
  ✔ Arrow keys — 1mm normal, 0.1mm Shift کے ساتھ
  ✔ Text cutting fix — Qt.TextDontClip flag
  ✔ PrinterResolution mode — label printers کے لیے بہتر

پرانے فیچرز (v2.0.0):
  ✔ بارکوڈ آن/آف ٹوگل
  ✔ اسٹیکر ایڈیٹر — drag/resize/rotate
  ✔ فونٹ فیملی، سائز، bold، italic، color
  ✔ ملی میٹر اور انچ
  ✔ Save as PDF

پرانے فیچرز (v1.0):
  ✔ EAN-13 بارکوڈ
  ✔ کمپنی نام، پروڈکٹ کوڈ، Mfg/Exp ڈیٹ، موبائل
  ✔ A4 شیٹ + لیبل پرنٹر موڈ
  ✔ CSV سے بلک امپورٹ
  ✔ SQLite ہسٹری
  ✔ English + Urdu

------------------------------------------------------------
 1. انسٹالیشن / INSTALLATION
------------------------------------------------------------

  طریقہ 1 — تیار شدہ انسٹالر:
    1. Setup.exe ڈبل کلک کریں
    2. Wizard کی ہدایات پر عمل کریں

  طریقہ 2 — GitHub سے ڈاؤن لوڈ:
    https://github.com/mohsinrasheed-Baga1/barcode-generator-pro/releases

------------------------------------------------------------
 2. پرنٹ کرنے کے تین طریقے / THREE WAYS TO PRINT
------------------------------------------------------------

  ➤ 🖨 Print (Custom Dialog — تجویز کردہ):
    1. "Print" بٹن دبائیں
    2. ایک custom dialog کھلے گی:
       • Printer dropdown سے پرنٹر منتخب کریں
         (Default پرنٹر خود کار طور پر selected ہوگا)
       • "⚙ Printer Properties" بٹن سے label size set کریں
       • Copies: 1-999
       • "Print" بٹن دبائیں
    3. کامیابی پر status message + popup دکھائی دے گا

  ➤ ⚡ Quick Print (فوری):
    1. "Quick Print" بٹن دبائیں
    2. Copies count پوچھی جائے گی
    3. ڈیفالٹ پرنٹر پر فوراً پرنٹ بھیج دیا جائے گا

  ➤ 📄 Save as PDF (Backup):
    1. "Save as PDF" بٹن دبائیں
    2. PDF فائل محفوظ کریں
    3. Adobe Acrobat / Microsoft Edge میں کھولیں
    4. **Important**: Print dialog میں "Actual Size" select کریں
       (NOT Fit یا Shrink to fit — ورنہ بارکوڈ غلط سائز میں نکلے گا)
    5. Print دبائیں

------------------------------------------------------------
 3. اگر پرنٹ نہ نکلے / TROUBLESHOOTING
------------------------------------------------------------

  مسئلہ: "Could not open the print dialog" error
  حل:    "Print" بٹن (custom dialog) استعمال کریں — یہ QPrintDialog
         کے بجائے ہماری اپنی dialog ہے جو reliable ہے۔
         اگر یہ بھی fail ہو تو "Quick Print" try کریں۔
         آخر میں "Save as PDF" ہمیشہ کام کرتا ہے۔

  مسئلہ: پرنٹ غلط سائز میں نکل رہا ہے
  حل:    "⚙ Printer Properties" بٹن دبائیں اور label size وہاں
         set کریں جو سافٹ ویئر میں selected ہے۔

  مسئلہ: PDF پرنٹ غلط نکل رہا ہے
  حل:    PDF viewer (Acrobat / Edge) کے Print dialog میں
         "Page Sizing" → "Actual size" select کریں۔
         "Fit" یا "Shrink to fit" select نہ کریں۔

  مسئلہ: بارکوڈ اسکین نہیں ہو رہا
  حل:    پرنٹ کوالٹی کم از کم 300 DPI پر رکھیں۔

  مسئلہ: کوئی پرنٹر نظر نہیں آ رہا
  حل:    Windows Settings > Printers & scanners میں جا کر
         کوئی پرنٹر "Set as default" کریں۔ یا "Microsoft Print
         to PDF" بھی کام کرتا ہے۔

------------------------------------------------------------
 4. اسٹیکر ایڈیٹر / STICKER LAYOUT EDITOR
------------------------------------------------------------

  "✏ Edit Sticker Layout" بٹن دبائیں۔ ہر عنصر کو:
  - ماؤس سے drag کر کے move کریں (جتنا چاہیں)
  - Arrow keys سے nudge کریں (1mm / Shift+arrow = 0.1mm)
  - Delete key سے disable کریں
  - Width/Height fields سے resize کریں
  - Rotation 0-360°
  - Font family, size, bold, italic, color, alignment

------------------------------------------------------------
 5. اکائیاں / UNITS (mm / in)
------------------------------------------------------------

  Settings میں "Measurement Units" سے mm یا in منتخب کریں۔

------------------------------------------------------------
 6. ڈیٹا / DATA
------------------------------------------------------------

  ڈیٹا SQLite ڈیٹابیس میں محفوظ ہے:
    %APPDATA%\BarcodeGenerator\barcodes.db
  Settings > Data ٹیب سے history صاف کر سکتے ہیں۔
