"""
core/embeddings.py
------------------
Local text embeddings, no API key, no model download.

The recruiting screen needs to say "which of these CVs is closest to this job",
in French, on a machine that may be fully offline (venue wifi is unreliable and
a customer's staff data must never leave their laptop). A hosted embedding API
would break both constraints. So we embed **locally** with a TF-IDF vector space
over word and character n-grams (scikit-learn), which is a genuine, deterministic
vector representation of the text:

    text  ->  L2-normalised sparse vector  ->  cosine similarity = dot product

Character n-grams (char_wb) matter a lot for Algerian French CVs: they absorb the
accent/spelling noise ("expérience" vs "experience", "diplome" vs "diplôme") and
match sub-words, so "logisticien" still lands near "logistique". Word n-grams
carry the meaning. We union the two.

This is not a transformer, and it does not pretend to be: it is a transparent,
reproducible local embedding that runs in milliseconds and needs no key. The
richer semantic judgement (why a candidate fits) is layered on top by
core/cv_screen.evaluate_freeform when an AI key is present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

# French stop words kept short and hand-picked: the sklearn 'french' list does
# not exist, and a heavy NLTK dependency is unwanted. These are the filler words
# that carry no signal in a CV or a job ad.
_FR_STOP = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "a", "au",
    "aux", "en", "dans", "pour", "par", "sur", "avec", "sans", "the", "of",
    "je", "il", "elle", "nous", "vous", "ce", "cette", "ces", "son", "sa",
    "ses", "mon", "ma", "mes", "est", "sont", "ans", "an", "plus", "chez",
    "que", "qui", "dans", "d", "l", "n", "s", "y",
}


def normalise(s: str) -> str:
    """Lowercase and strip French accents so spelling variants collapse."""
    s = str(s).lower()
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"), ("à", "a"),
                 ("â", "a"), ("ä", "a"), ("î", "i"), ("ï", "i"), ("ô", "o"),
                 ("ö", "o"), ("û", "u"), ("ù", "u"), ("ü", "u"), ("ç", "c")):
        s = s.replace(a, b)
    return s


@dataclass
class EmbeddingSpace:
    """A fitted TF-IDF space you can transform new text into and compare within."""
    _word_vec: object
    _char_vec: object
    _word_w: float
    _char_w: float

    def transform(self, texts: Sequence[str]) -> np.ndarray:
        """Embed texts into the (dense) unit-normalised vector space."""
        from sklearn.preprocessing import normalize
        from scipy.sparse import hstack

        docs = [normalise(t) for t in texts]
        w = self._word_vec.transform(docs) * self._word_w
        c = self._char_vec.transform(docs) * self._char_w
        mat = hstack([w, c]).tocsr()
        return normalize(mat, norm="l2", copy=False)

    def similarity(self, a: Sequence[str], b: Sequence[str]) -> np.ndarray:
        """Cosine similarity matrix between texts `a` (rows) and `b` (cols)."""
        from sklearn.metrics.pairwise import linear_kernel
        va, vb = self.transform(a), self.transform(b)
        return linear_kernel(va, vb)

    def top_terms(self, text: str, k: int = 8) -> list:
        """The highest-weight word terms in a text — for 'why this matched'."""
        vec = self._word_vec
        row = vec.transform([normalise(text)]).tocoo()
        try:
            names = vec.get_feature_names_out()
        except Exception:
            names = np.array(vec.get_feature_names())
        pairs = sorted(zip(row.col, row.data), key=lambda p: p[1], reverse=True)
        out, seen = [], set()
        for col, _ in pairs:
            term = names[col]
            if term in seen:
                continue
            seen.add(term)
            out.append(term)
            if len(out) >= k:
                break
        return out


def fit(corpus: Sequence[str], *, word_weight: float = 1.0,
        char_weight: float = 0.6) -> EmbeddingSpace:
    """
    Fit a local embedding space on a corpus (all the CVs + the job text).

    Fitting on the documents actually being compared keeps the vocabulary tight
    and the vectors meaningful even for a handful of CVs.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    docs = [normalise(t) for t in corpus] or [""]
    word_vec = TfidfVectorizer(
        analyzer="word", ngram_range=(1, 2), min_df=1,
        stop_words=list(_FR_STOP), sublinear_tf=True,
    )
    char_vec = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True,
    )
    word_vec.fit(docs)
    char_vec.fit(docs)
    return EmbeddingSpace(word_vec, char_vec, word_weight, char_weight)


def cosine(a: str, b: str) -> float:
    """Convenience: cosine similarity of two strings in their own little space."""
    space = fit([a, b])
    return float(space.similarity([a], [b])[0, 0])


if __name__ == "__main__":
    print("Local embeddings — self check\n")
    job = "Agent de tri logistique, scan des colis, gestion de stock, manutention"
    cvs = {
        "Logisticien": "Licence en logistique, experience en tri de colis, scan, stock",
        "Cuisinier": "Chef cuisinier, restauration, gestion de salle et de menus",
        "Magasinier": "Magasinier, manutention, inventaire et gestion de stock entrepot",
    }
    space = fit([job] + list(cvs.values()))
    sims = space.similarity([job], list(cvs.values()))[0]
    for (name, _), s in sorted(zip(cvs.items(), sims), key=lambda z: z[1], reverse=True):
        print(f"  {s:5.3f}  {name}")
    print("\n  accent robustness  cos('experience','expérience') =",
          round(cosine("experience", "expérience"), 3))
    print("  job top terms:", space.top_terms(job, 6))
