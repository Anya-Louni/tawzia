"""
core/pii.py
-----------
Personal-data masking before any call to an outside model (law 25-11, brief
§8.4).

Names, phones, NIN, RIB, emails and ID numbers are replaced by tokens
([PERSON_1], [PHONE_1]...) before sending, then put back in the answer. The model
never sees who is who. Names come from the staff file: a name absent from the
file is not recognised, hence the patterns for everything that has a format.
"""

from __future__ import annotations

import re

PATTERNS = [
    ("RIB", re.compile(r"\b\d{20}\b")),
    ("NIN", re.compile(r"\b\d{18}\b")),
    ("PHONE", re.compile(r"(?:\+213|\b0)[\s.-]?[5-7](?:[\s.-]?\d){8}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
]


def redact(text: str, names: list | tuple = ()) -> tuple[str, dict]:
    """(masked text, token -> original value table)."""
    table, seen = {}, {}

    def token(kind: str, value: str) -> str:
        if value not in seen:
            seen[value] = f"[{kind}_{sum(1 for k in seen.values() if k.startswith('[' + kind)) + 1}]"
            table[seen[value]] = value
        return seen[value]

    out = text
    for kind, rx in PATTERNS:
        out = rx.sub(lambda m: token(kind, m.group(0)), out)
    # Full names first, longest before shortest.
    for n in sorted({n for n in names if n}, key=len, reverse=True):
        rx = re.compile(re.escape(n), re.IGNORECASE)
        out = rx.sub(lambda m: token("PERSON", n), out)
    return out, table


def restore(text: str, table: dict) -> str:
    for tok, value in table.items():
        text = text.replace(tok, value)
    return text


if __name__ == "__main__":
    src = ("Amina Belkacem (0551 23 45 67, amina@exemple.dz, NIN 109876543210987654, "
           "RIB 00799999000123456789) asks for a certificate. Amina Belkacem is on a CDI.")
    red, t = redact(src, ["Amina Belkacem", "Yacine Haddad"])
    for leak in ("Amina", "0551", "@", "109876543210987654", "00799999000123456789"):
        assert leak not in red, (leak, red)
    assert red.count("[PERSON_1]") == 2
    assert restore(red, t) == src
    print("  personal-data masking: ok")
