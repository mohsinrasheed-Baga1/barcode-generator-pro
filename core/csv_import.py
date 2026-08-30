"""
CSV importer for bulk barcode generation.
Expected columns (case-insensitive, flexible):
    company_name, product_name, product_code, barcode,
    mfg_date, exp_date, mobile
"""
import csv
import io


REQUIRED_FIELDS = ['barcode']
OPTIONAL_FIELDS = ['company_name', 'product_name', 'product_code',
                   'mfg_date', 'exp_date', 'mobile']


def _normalize_header(h: str) -> str:
    return (h or '').strip().lower().replace(' ', '_')


def import_csv(file_path: str, default_company: str = '',
               default_mobile: str = '') -> list:
    """
    Returns a list of dicts with keys:
        company_name, product_name, product_code, barcode,
        mfg_date, exp_date, mobile
    Raises ValueError on malformed file.
    """
    rows = []
    with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
        # Try to sniff delimiter, default to comma
        try:
            sample = f.read(2048)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("CSV file has no header row.")
        headers = [_normalize_header(h) for h in reader.fieldnames]
        if 'barcode' not in headers:
            raise ValueError(
                "CSV must contain a 'barcode' column (other columns are optional)."
            )
        # Build a mapping from normalized header -> original
        col_map = {norm: orig for orig, norm in zip(reader.fieldnames, headers)}

        for i, row in enumerate(reader, start=2):  # row 1 is header
            entry = {}
            for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
                if field in col_map:
                    val = row.get(col_map[field], '') or ''
                else:
                    val = ''
                entry[field] = val.strip()
            if not entry.get('barcode'):
                # skip blank rows
                continue
            # apply defaults
            if not entry.get('company_name'):
                entry['company_name'] = default_company
            if not entry.get('mobile'):
                entry['mobile'] = default_mobile
            rows.append(entry)
    return rows


def write_csv_template(file_path: str):
    """Write a sample CSV template."""
    headers = ['company_name', 'product_name', 'product_code', 'barcode',
               'mfg_date', 'exp_date', 'mobile']
    sample = [
        {'company_name': 'ABC Traders', 'product_name': 'Sunlight Soap',
         'product_code': 'SL-001', 'barcode': '501234567890',
         'mfg_date': '2025-01-01', 'exp_date': '2026-01-01', 'mobile': '+923001234567'},
        {'company_name': 'ABC Traders', 'product_name': 'Tea Pack 200g',
         'product_code': 'TEA-200', 'barcode': '501234567891',
         'mfg_date': '2025-02-15', 'exp_date': '2026-08-15', 'mobile': '+923001234567'},
        {'company_name': 'ABC Traders', 'product_name': 'Rice 1kg',
         'product_code': 'RC-1KG', 'barcode': '501234567892',
         'mfg_date': '2025-03-10', 'exp_date': '2026-09-10', 'mobile': '+923001234567'},
    ]
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(sample)
