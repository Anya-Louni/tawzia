"""
core/law_corpus.py
------------------
The small legal corpus cited by the assistant and the MCP server.

These are **summaries**, not the official text: each entry states what
the article provides, in one or two sentences, and links to the text. The corpus only
covers the articles that the platform applies. A question that is not answered
there goes to the HR service: the system never guesses a right.
"""

from __future__ import annotations

import unicodedata

WIPO_90_11 = "https://www.wipo.int/wipolex/edocs/lexdocs/laws/fr/dz/dz039fr.html"
JO_25_11 = "https://droit.mjustice.gov.dz/sites/default/files/loi_25-11-fr.pdf"

ARTICLES = [
    ("90-11/12", "Law 90-11", "art. 12", "Fixed-term contract",
     "A CDD is only allowed in listed cases: replacement of a holder, "
     "temporary or seasonal increase, temporary work by nature.", WIPO_90_11),
    ("90-11/18", "Law 90-11", "art. 18", "Probation period",
     "The probation period has a maximum duration, longer for high‑qualification positions. The platform applies the values from its configuration "
     "(10 and 12 months) [to be verified against the text].", WIPO_90_11),
    ("90-11/20", "Law 90-11", "art. 20", "Termination during probation",
     "During probation, either party may terminate without notice or compensation.", WIPO_90_11),
    ("90-11/27", "Law 90-11", "art. 27", "Night work",
     "Night work is work performed between 9 p.m. and 5 a.m.", WIPO_90_11),
    ("90-11/28", "Law 90-11", "art. 28", "Night work and age",
     "Workers under 19 years old may not work at night.", WIPO_90_11),
    ("90-11/29", "Law 90-11", "art. 29", "Night work and women",
     "Night work for women requires a waiver from the territorially competent labor inspector.", WIPO_90_11),
    ("90-11/31", "Law 90-11", "art. 31", "Overtime",
     "Overtime may not exceed 20 % of the legal duration.", WIPO_90_11),
    ("90-11/32", "Law 90-11", "art. 32", "Overtime premium",
     "Each overtime hour is increased by at least 50 % of the normal hourly wage.", WIPO_90_11),
    ("90-11/33", "Law 90-11", "art. 33", "Weekly rest",
     "The worker is entitled to a full day of rest per week, usually on Friday.", WIPO_90_11),
    ("90-11/36", "Law 90-11", "art. 36", "Compensatory rest",
     "Work on a legal rest day gives rise to an equal‑duration compensatory rest.", WIPO_90_11),
    ("90-11/37", "Law 90-11", "art. 37", "Rest day shift",
     "The weekly rest may be shifted for production reasons.", WIPO_90_11),
    ("90-11/40", "Law 90-11", "art. 40", "Reference year for leave",
     "Leave entitlement is calculated on the year from July 1 to June 30.", WIPO_90_11),
    ("90-11/41", "Law 90-11", "art. 41", "Annual leave duration",
     "Two and a half days per month of work, up to a maximum of 30 calendar days per year.", WIPO_90_11),
    ("90-11/42", "Law 90-11", "art. 42", "Leave in the South",
     "Workers in the southern wilayas receive at least ten additional days.", WIPO_90_11),
    ("90-11/54", "Law 90-11", "art. 54", "Special paid absences",
     "Three paid working days for certain listed family events (marriage, birth, death of a close relative).", WIPO_90_11),
    ("90-11/75", "Law 90-11", "art. 75", "Internal regulations",
     "Mandatory in employer organizations with at least 20 workers.", WIPO_90_11),
    ("97-03", "Ordinance 97-03", "art. 2", "Legal duration",
     "The legal working time is 40 hours per week.", WIPO_90_11),
    ("20-03", "Law 04-19 amended by Law 20-03", "", "Job offer and ANEM",
     "The employer submits its offers to the employment services; ANEM has five working days to propose candidates before any direct recruitment.", 
     "https://blog.emploitic.com/index.php/delai-de-traitement-de-loffre-demploi-par-lanem-et-organismes-de-recrutement-prives/"),
    ("25-11", "Law 18-07 amended by Law 25-11", "", "Personal data",
     "Employee data processing is tracked (collection, consultation, modification, deletion) and transfers abroad require safeguards.", JO_25_11),
]

FIELDS = ("id", "text", "article", "title", "summary", "url")


def _plain(s: str) -> str:
    t = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def search(query: str, limit: int = 5) -> list:
    """Articles whose title or summary share the most words with the question."""
    words = [w for w in _plain(query).replace("'", " ").split() if len(w) > 2]
    scored = []
    for row in ARTICLES:
        hay = _plain(" ".join(row[1:5]))
        score = sum(hay.count(w) for w in words) + (3 if _plain(row[2]) in _plain(query) and row[2] else 0)
        if score:
            scored.append((score, dict(zip(FIELDS, row))))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:limit]]


if __name__ == "__main__":
    assert search("night work women")[0]["article"] in ("art. 29", "art. 27")
    assert search("overtime cap")[0]["article"] == "art. 31"
    assert search("leave south")[0]["article"] == "art. 42"
    assert search("xyzzy") == []
    print("  law corpus: ok")
