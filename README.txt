============================================================
  BARCODE GENERATOR PRO  (EAN-13)  —  v5.0.0
  بارکوڈ جنریٹر پرو
============================================================

نئے فیچرز (v5.0.0):
  ✔ 🏷 Speed-X SP 700U presets شامل:
    • 110×25 mm sheet (3 stickers per row, each 32×25 mm)
    • 32×25 mm single sticker
  ✔ 📊 Barcode visibility fix — module dimensions اب mm میں
    convert ہوتے ہیں (پہلے px تھے، جس سے barcode غلط سائز میں
    render ہوتا تھا یا نظر نہیں آتا تھا)
  ✔ 📊 Barcode error display — اگر barcode generate نہ ہو سکے
    تو error message sticker پر دکھائی دے گا

پرانے فیچرز (v2.2.0):
  ✔ Illustrator-like editor (9 handles + cursor feedback)
  ✔ Responsive UI (QSplitter + scrollable panels)

------------------------------------------------------------
 Speed-X SP 700U پرنٹر کے لیے استعمال
------------------------------------------------------------

  آپ کے پرنٹر کے لیے دو presets تیار ہیں:

  1. "★ [Speed-X SP 700U] 110×25 mm sheet — 3 stickers per row"
     • Sheet size: 110×25 mm
     • 3 stickers per sheet, each 32×25 mm
     • Layout: [32mm] [5mm gap] [32mm] [5mm gap] [32mm]
     • استعمال: جب ایک ساتھ 3 stickers پرنٹ کرنا ہوں

  2. "★ [Speed-X SP 700U] 32×25 mm — single sticker"
     • Sticker size: 32×25 mm
     • استعمال: جب ایک وقت میں ایک sticker پرنٹ کرنا ہو

  طریقہ:
    1. Layout dropdown میں سے appropriate preset select کریں
    2. اپنا data enter کریں
    3. "Add to Sheet" دبائیں (3-up کے لیے 3 items add کریں)
    4. "🖨 Print" دبائیں
    5. Print Setup dialog میں Speed-X SP 700U select کریں
    6. "⚙ Printer Properties" میں label size وہی set کریں
       (110×25 mm یا 32×25 mm، preset کے مطابق)
    7. Print دبائیں

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
