"""
core/rules.py
-------------
The dated Algerian payroll rules, read from config/dz_payroll_<year>.toml.

Every legal rate lives in that file, never in code: a new finance law means a
new file with its own `valid_from`, and this loader picks the latest one
already in force.
"""

from __future__ import annotations

import datetime as _dt
import tomllib
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@lru_cache(maxsize=8)
def payroll(as_of: _dt.date | None = None) -> dict:
    as_of = as_of or _dt.date.today()
    files = []
    for f in CONFIG_DIR.glob("dz_payroll_*.toml"):
        cfg = tomllib.loads(f.read_text(encoding="utf-8"))
        if cfg["valid_from"] <= as_of:
            files.append(cfg)
    if not files:
        raise RuntimeError(f"No payroll rules in force on {as_of} in {CONFIG_DIR}")
    return max(files, key=lambda c: c["valid_from"])


def cnas_rates(as_of: _dt.date | None = None) -> tuple[float, float]:
    """(employer, employee) totals, summed from the branch table."""
    branches = payroll(as_of)["cnas"].values()
    return (round(sum(b[0] for b in branches), 4),
            round(sum(b[1] for b in branches), 4))
