"""
SQLite database for barcode history.
"""
import os
import sqlite3
from datetime import datetime

from PyQt5.QtCore import QStandardPaths


def get_db_path() -> str:
    """Get the user-data database path (works on Windows: %APPDATA%/BarcodeGenerator)."""
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    if not base:
        # Fallback to home dir
        base = os.path.join(os.path.expanduser('~'), 'BarcodeGenerator')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, 'barcodes.db')


SCHEMA = """
CREATE TABLE IF NOT EXISTS barcodes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name  TEXT,
    product_name  TEXT,
    product_code  TEXT,
    barcode       TEXT,
    mfg_date      TEXT,
    exp_date      TEXT,
    mobile        TEXT,
    created_at    TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class Database:
    def __init__(self, path: str = None):
        self.path = path or get_db_path()
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    # --- barcode history ---
    def save_barcode(self, data: dict) -> int:
        with self.conn:
            cur = self.conn.execute(
                """INSERT INTO barcodes
                   (company_name, product_name, product_code, barcode,
                    mfg_date, exp_date, mobile, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    data.get('company_name', ''),
                    data.get('product_name', ''),
                    data.get('product_code', ''),
                    data.get('barcode', ''),
                    data.get('mfg_date', ''),
                    data.get('exp_date', ''),
                    data.get('mobile', ''),
                    datetime.now().isoformat(timespec='seconds'),
                )
            )
            return cur.lastrowid

    def list_barcodes(self, limit: int = 500) -> list:
        cur = self.conn.execute(
            "SELECT * FROM barcodes ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in cur.fetchall()]

    def search_barcodes(self, query: str) -> list:
        q = f"%{query}%"
        cur = self.conn.execute(
            """SELECT * FROM barcodes
               WHERE company_name LIKE ? OR product_name LIKE ?
                  OR product_code LIKE ? OR barcode LIKE ? OR mobile LIKE ?
               ORDER BY id DESC LIMIT 500""",
            (q, q, q, q, q)
        )
        return [dict(r) for r in cur.fetchall()]

    def delete_barcode(self, id_: int):
        with self.conn:
            self.conn.execute("DELETE FROM barcodes WHERE id = ?", (id_,))

    def clear_history(self):
        with self.conn:
            self.conn.execute("DELETE FROM barcodes")

    # --- settings ---
    def get_setting(self, key: str, default=None):
        cur = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = cur.fetchone()
        return row['value'] if row else default

    def set_setting(self, key: str, value):
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value if isinstance(value, str) else str(value))
            )
