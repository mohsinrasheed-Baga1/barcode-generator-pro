"""
Unit conversion helpers — millimeters and inches.
"""
from dataclasses import dataclass


MM_PER_INCH = 25.4
PT_PER_INCH = 72.0
MM_PER_PT = MM_PER_INCH / PT_PER_INCH


@dataclass
class Unit:
    code: str
    label: str
    symbol: str
    to_mm_factor: float

    def to_mm(self, value: float) -> float:
        return value * self.to_mm_factor

    def from_mm(self, mm: float) -> float:
        return mm / self.to_mm_factor


MM = Unit(code='mm', label='Millimeters', symbol='mm', to_mm_factor=1.0)
IN = Unit(code='in', label='Inches', symbol='in', to_mm_factor=MM_PER_INCH)

UNITS = {MM.code: MM, IN.code: IN}


def get_unit(code: str) -> Unit:
    return UNITS.get(code, MM)


def pt_to_mm(pt: float) -> float:
    return pt * MM_PER_PT


def mm_to_pt(mm: float) -> float:
    return mm / MM_PER_PT


def format_value(mm: float, unit: Unit, decimals: int = 2) -> str:
    val = unit.from_mm(mm)
    return f"{val:.{decimals}f} {unit.symbol}"
