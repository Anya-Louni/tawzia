"""
core/bias.py
------------
The fairness audit of candidate ranking: selection rate by gender (and by age
band when known), and the four-fifths rule.

The rule: if a group's selection rate falls below 80% of the best-selected
group's, it is an adverse-impact signal to examine. It is the US benchmark
(EEOC) that New York's required bias audits (Local Law 144) build on; the EU AI
Act classes hiring AI as high risk. Tawzia aligns with them without being bound
by Algerian law to do so.

The score itself never reads the name or gender: the audit looks at the outcome,
not the input.
"""

from __future__ import annotations

SELECTED = ("strong", "possible")
MIN_GROUP = 5   # below this, the gap cannot be interpreted

GENDER_FR = {"F": "Women", "M": "Men"}


def four_fifths(screenings: list, attr: str = "gender") -> dict:
    groups = {}
    for s in screenings:
        g = getattr(s.candidate, attr, None)
        if not g:
            continue
        n, k = groups.get(g, (0, 0))
        groups[g] = (n + 1, k + (1 if s.band in SELECTED else 0))
    rates = {g: k / n for g, (n, k) in groups.items() if n}
    top = max(rates.values()) if rates else 0
    rows = []
    for g, (n, k) in sorted(groups.items()):
        ratio = rates[g] / top if top else 1.0
        rows.append({"group": g, "label": GENDER_FR.get(g, g), "candidates": n,
                     "selected": k, "rate": round(rates[g], 3),
                     "ratio_to_top": round(ratio, 3),
                     "flag": n >= MIN_GROUP and ratio < 0.8,
                     "small_sample": n < MIN_GROUP})
    return {"rows": rows, "ok": not any(r["flag"] for r in rows),
            "rule": "Four-fifths rule: a group below 80% of the best-selected "
                    "group's rate is flagged."}


if __name__ == "__main__":
    from types import SimpleNamespace as N
    mk = lambda g, b: N(candidate=N(gender=g), band=b)  # noqa: E731
    pool = [mk("M", "strong")] * 6 + [mk("M", "weak")] * 4 + [mk("F", "strong")] * 2 + [mk("F", "weak")] * 6
    r = four_fifths(pool)
    f = next(x for x in r["rows"] if x["group"] == "F")
    assert not r["ok"] and f["flag"] and f["ratio_to_top"] == round(0.25 / 0.6, 3)
    assert four_fifths([mk("M", "strong")] * 5 + [mk("F", "strong")] * 5)["ok"]
    print("  fairness audit: ok")
