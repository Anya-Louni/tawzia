"""
core/bias.py
------------
L'audit d'équité du tri des candidatures : taux de sélection par genre (et par
tranche d'âge si elle est connue), et la règle des quatre cinquièmes.

La règle : si le taux de sélection d'un groupe tombe sous 80 % de celui du
groupe le mieux sélectionné, c'est un signal d'impact défavorable à examiner.
C'est la référence américaine (EEOC) que reprennent les audits de biais exigés
à New York (Local Law 144) ; l'IA de recrutement est classée à haut risque par
l'AI Act européen. Tawzia s'y aligne sans y être tenue par le droit algérien.

Le score lui-même ne lit jamais le nom ni le genre : l'audit regarde le
résultat, pas l'entrée.
"""

from __future__ import annotations

SELECTED = ("strong", "possible")
MIN_GROUP = 5   # en dessous, l'écart n'est pas interprétable

GENDER_FR = {"F": "Femmes", "M": "Hommes"}


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
            "rule": "Règle des quatre cinquièmes : un groupe sous 80 % du taux du "
                    "groupe le mieux sélectionné est signalé."}


if __name__ == "__main__":
    from types import SimpleNamespace as N
    mk = lambda g, b: N(candidate=N(gender=g), band=b)  # noqa: E731
    pool = [mk("M", "strong")] * 6 + [mk("M", "weak")] * 4 + [mk("F", "strong")] * 2 + [mk("F", "weak")] * 6
    r = four_fifths(pool)
    f = next(x for x in r["rows"] if x["group"] == "F")
    assert not r["ok"] and f["flag"] and f["ratio_to_top"] == round(0.25 / 0.6, 3)
    assert four_fifths([mk("M", "strong")] * 5 + [mk("F", "strong")] * 5)["ok"]
    print("  audit d'équité : ok")
