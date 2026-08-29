"""
History dialog - list/search previously saved barcodes; click to reuse.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableView, QHeaderView, QMessageBox
)
from PyQt5.QtCore import QAbstractTableModel, QModelIndex

from core.database import Database


class HistoryDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("History / ہسٹری")
        self.resize(820, 540)
        self.selected_entry = None

        v = QVBoxLayout(self)

        # Search bar
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍 Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Company, product, code, barcode, mobile...")
        self.search_edit.textChanged.connect(self.on_search_changed)
        search_row.addWidget(self.search_edit)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_data)
        search_row.addWidget(self.refresh_btn)
        v.addLayout(search_row)

        # Table
        self.model = QStandardItemModel(0, 7)
        self.model.setHorizontalHeaderLabels(
            ["ID", "Date", "Company", "Product", "Code", "Barcode", "Mobile"]
        )
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.SingleSelection)
        self.table.setEditTriggers(self.table.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.on_double_click)
        v.addWidget(self.table)

        # Buttons
        btn_row = QHBoxLayout()
        self.use_btn = QPushButton("✓ Use Selected")
        self.use_btn.clicked.connect(self.on_use_clicked)
        btn_row.addWidget(self.use_btn)
        self.del_btn = QPushButton("🗑 Delete Selected")
        self.del_btn.clicked.connect(self.on_delete_clicked)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch(1)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.close_btn)
        v.addLayout(btn_row)

        self.load_data()

    def load_data(self):
        q = self.search_edit.text().strip()
        if q:
            rows = self.db.search_barcodes(q)
        else:
            rows = self.db.list_barcodes()
        self.model.removeRows(0, self.model.rowCount())
        for r in rows:
            self.model.appendRow([
                QStandardItem(str(r.get('id', ''))),
                QStandardItem(r.get('created_at', '')[:19]),
                QStandardItem(r.get('company_name', '')),
                QStandardItem(r.get('product_name', '')),
                QStandardItem(r.get('product_code', '')),
                QStandardItem(r.get('barcode', '')),
                QStandardItem(r.get('mobile', '')),
            ])

    def on_search_changed(self, _):
        self.load_data()

    def current_row(self) -> dict:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        row = idx.row()
        # Build entry from model
        def g(col):
            return self.model.item(row, col).text() if self.model.item(row, col) else ''
        return {
            'id': int(g(0)) if g(0).isdigit() else None,
            'created_at': g(1),
            'company_name': g(2),
            'product_name': g(3),
            'product_code': g(4),
            'barcode': g(5),
            'mobile': g(6),
            # dates — we don't include them here; could be added if needed
            'mfg_date': '',
            'exp_date': '',
        }

    def on_use_clicked(self):
        entry = self.current_row()
        if entry is None:
            QMessageBox.information(self, "Select",
                                    "Please select a row first.")
            return
        self.selected_entry = entry
        self.accept()

    def on_double_click(self, _):
        self.on_use_clicked()

    def on_delete_clicked(self):
        entry = self.current_row()
        if entry is None or entry.get('id') is None:
            return
        ok = QMessageBox.question(
            self, "Confirm",
            f"Delete entry #{entry['id']}?"
        )
        if ok == QMessageBox.Yes:
            self.db.delete_barcode(entry['id'])
            self.load_data()
