"""
core/matching.py
----------------
Appariement CV / poste par embeddings locaux.

Given one job description (in the employer's own words) and a batch of CVs, rank
the candidates by fit — entirely locally, no API key. The ranking blends two
signals that answer two different questions:

  * **Similarité sémantique** (core/embeddings): how close is the whole CV to the
    whole job ad, in the local TF-IDF vector space. Catches relevance the rubric
    misses ("cariste" near "manutention"), robust to French spelling/accents.
  * **Adéquation structurée** (core/cv_screen): the deterministic Algerian rubric
    — formation LMD, expérience, langues, permis, service national, mobilité.
    Catches hard gates the raw text similarity would gloss over.

The blended score is transparent: each candidate row shows the embedding
similarity, the structured score, the shared key terms that drove the match, and
the rubric's own flags. Fully reproducible — same inputs, same ranking.

An AI key is never required here; when one is present the recruiting page can add
core/cv_screen.evaluate_freeform on top for a written verdict per candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import cv_screen, embeddings


@dataclass
class Match:
    label: str                 # the CV's label / candidate name
    similarity: float          # 0..1 cosine similarity CV vs job
    structured: int            # 0..100 rubric score
    blended: int               # 0..100 final rank score
    band: str                  # fort | possible | faible
    shared_terms: list         # terms present in both job and CV
    flags: list                # rubric flags (missing language, licence, ...)
    method: str                # "rules" | "ai" (extraction method)


_BAND_FR = {"strong": "fort", "possible": "possible", "weak": "faible"}


def _band(pct: int) -> str:
    return "fort" if pct >= 70 else ("possible" if pct >= 45 else "faible")


def rank_cvs(
    job_text: str,
    cvs: dict,
    *,
    job: Optional[cv_screen.Job] = None,
    use_ai: bool = False,
    sim_weight: float = 0.5,
) -> list:
    """
    Rank a batch of CVs against a free-text job description.

    `cvs` maps a label (candidate name / filename) -> CV text.
    `sim_weight` splits the blend between embedding similarity and the structured
    rubric (0.5 = equal). Returns a list of `Match`, best first.
    """
    if not cvs:
        return []

    labels = list(cvs)
    texts = [cvs[l] for l in labels]

    # Local embedding similarity: fit on job + all CVs, compare job to each CV.
    space = embeddings.fit([job_text] + texts)
    sims = space.similarity([job_text], texts)[0]

    def _unigrams(terms):
        return {w for t in terms for w in t.split() if len(w) > 2}

    job_terms = _unigrams(space.top_terms(job_text, 40))

    matches = []
    for label, text, sim in zip(labels, texts, sims):
        sim = float(max(0.0, min(1.0, sim)))
        shared = sorted(job_terms & _unigrams(space.top_terms(text, 60)))[:8]

        if job is not None:
            scr = cv_screen.screen(text, job, use_ai=use_ai)
            structured, flags, method = scr.score, scr.flags, scr.method
        else:
            # No structured job template: lean on similarity, scaled to a score.
            structured = int(round(sim * 100))
            flags, method = [], "rules"

        blended = int(round((sim_weight * sim * 100) +
                            ((1 - sim_weight) * structured)))
        blended = max(0, min(100, blended))
        matches.append(Match(
            label=label, similarity=round(sim, 3), structured=structured,
            blended=blended, band=_band(blended), shared_terms=shared,
            flags=flags, method=method,
        ))

    return sorted(matches, key=lambda m: (m.blended, m.similarity), reverse=True)


def rank_frame(matches: list) -> pd.DataFrame:
    """The ranking as a tidy French table for the UI / export."""
    rows = []
    for i, m in enumerate(matches, 1):
        rows.append({
            "Rang": i,
            "Candidat": m.label,
            "Score global": m.blended,
            "Similarité poste": round(m.similarity * 100),
            "Score structuré": m.structured,
            "Verdict": m.band,
            "Termes communs": ", ".join(m.shared_terms) or "-",
            "Alertes": "; ".join(m.flags) or "-",
        })
    return pd.DataFrame(rows)


def match_job_key(job_text: str) -> Optional[str]:
    """
    Best-guess which built-in job template a free-text ad is closest to, so the
    structured rubric can be applied automatically. Uses the same local
    embeddings, so it stays offline.
    """
    keys = list(cv_screen.JOB_TEMPLATES_TEXT)
    templates = [cv_screen.JOB_TEMPLATES_TEXT[k] for k in keys]
    space = embeddings.fit([job_text] + templates)
    sims = space.similarity([job_text], templates)[0]
    best = int(sims.argmax())
    return keys[best] if sims[best] > 0.05 else None


if __name__ == "__main__":
    print("CV / poste matching by local embeddings — self check\n")
    job_text = cv_screen.JOB_TEMPLATES_TEXT["sorter"]
    key = match_job_key(job_text)
    print(f"  auto-detected job template: {key} "
          f"({cv_screen.JOBS[key].title if key in cv_screen.JOBS else key})\n")
    job = cv_screen.JOBS.get(key)
    ranked = rank_cvs(job_text, cv_screen.SAMPLE_CVS, job=job, use_ai=False)
    print(rank_frame(ranked).to_string(index=False))
