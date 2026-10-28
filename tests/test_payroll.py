"""
Payroll engine test vectors (rebuild spec section 7, checked against published
examples). Run: venv/Scripts/python.exe tests/test_payroll.py  (or pytest)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import payroll_dz as p  # noqa: E402


def test_snmg_is_exempt():
    s = p.payslip(24_000)
    assert round(s.cnas_employee) == 2_160
    assert round(s.taxable) == 21_840
    assert s.irg == 0


def test_60k():
    s = p.payslip(60_000)
    assert round(s.cnas_employee) == 5_400
    assert round(s.taxable) == 54_600
    assert round(s.irg) == 7_042
    assert round(s.net) == 47_558


def test_smoothing_band_top():
    assert round(p.irg_from_taxable(35_000)) == 2_070


def test_special_regime():
    assert abs(p.irg_from_taxable(32_000, special=True) - 543.9) < 0.1


def test_exemption_edge():
    assert p.irg_from_taxable(30_000) == 0


def test_no_negative_irg():
    assert p.irg_from_taxable(30_001) >= 0




def test_breakdown_matches_vector():
    b = p.pay_breakdown({"base": 60_000})
    assert (b["cnas_employee"], b["taxable"], b["irg"], b["net"]) == (5_400, 54_600, 7_042, 47_558)


def test_item_outside_cnas_base():
    b = p.pay_breakdown({"base": 40_000, "panier": 5_000})
    assert b["cnas_base"] == 40_000 and b["cnas_employee"] == 3_600
    assert b["taxable"] == 45_000 - 3_600


def test_employer_branches_sum_to_rate():
    b = p.pay_breakdown({"base": 100_000})
    assert b["employer_cnas"] == round(100_000 * p.CNAS_EMPLOYER)


def test_special_status_breakdown():
    # taxable 32,000 for a retiree: gross 32,000 / 0.91 gives CNAS-adjusted base
    assert p.pay_breakdown({"base": 24_000}, "retired")["irg"] == 0


def test_rejects_unknown_item():
    try:
        p.pay_breakdown({"bonus_mystere": 1})
    except ValueError:
        return
    raise AssertionError("unknown item accepted")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
