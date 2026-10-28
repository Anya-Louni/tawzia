"""
core/pii.py
-----------
Le masquage des données personnelles avant tout appel à un modèle extérieur
(loi 25-11, brief §8.4).

Noms, téléphones, NIN, RIB, courriels et numéros de pièce sont remplacés par
des jetons ([PERSONNE_1], [TEL_1]...) avant l'envoi, puis remis en place dans
la réponse. Le modèle ne voit jamais qui est qui. Les noms viennent du fichier
du personnel : un nom absent du fichier n'est pas reconnu, d'où les motifs pour
tout ce qui a un format.
"""

from __future__ import annotations

import re

PATTERNS = [
    ("RIB", re.compile(r"\b\d{20}\b")),
    ("NIN", re.compile(r"\b\d{18}\b")),
    ("TEL", re.compile(r"(?:\+213|\b0)[\s.-]?[5-7](?:[\s.-]?\d){8}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
]


def redact(text: str, names: list | tuple = ()) -> tuple[str, dict]:
    """(texte masqué, table jeton -> valeur d'origine)."""
    table, seen = {}, {}

    def token(kind: str, value: str) -> str:
        if value not in seen:
            seen[value] = f"[{kind}_{sum(1 for k in seen.values() if k.startswith('[' + kind)) + 1}]"
            table[seen[value]] = value
        return seen[value]

    out = text
    for kind, rx in PATTERNS:
        out = rx.sub(lambda m: token(kind, m.group(0)), out)
    # Les noms complets d'abord, les plus longs avant les plus courts.
    for n in sorted({n for n in names if n}, key=len, reverse=True):
        rx = re.compile(re.escape(n), re.IGNORECASE)
        out = rx.sub(lambda m: token("PERSONNE", n), out)
    return out, table


def restore(text: str, table: dict) -> str:
    for tok, value in table.items():
        text = text.replace(tok, value)
    return text


if __name__ == "__main__":
    src = ("Amina Belkacem (0551 23 45 67, amina@exemple.dz, NIN 109876543210987654, "
           "RIB 00799999000123456789) demande une attestation. Amina Belkacem est en CDI.")
    red, t = redact(src, ["Amina Belkacem", "Yacine Haddad"])
    for leak in ("Amina", "0551", "@", "109876543210987654", "00799999000123456789"):
        assert leak not in red, (leak, red)
    assert red.count("[PERSONNE_1]") == 2
    assert restore(red, t) == src
    print("  masquage des données personnelles : ok")
