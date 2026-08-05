"""
core/inspector.py
-----------------
The Inspection Simulator - a dry run of the labour inspection before the real
inspecteur du travail shows up.

It reuses the deterministic compliance checks (so every finding is a real,
rule-based fact, never an AI hallucination), then attaches to each finding the
article it rests on, an indicative fine band, and how likely an inspector is to
catch it. An optional AI layer writes the inspector's report and the cheapest
remediation order in plain words; without an API key a clear template is used.

Honesty: fine bands are INDICATIVE ranges for prioritisation, not legal advice.
Actual penalties are set by the labour code and the inspector's discretion. The
app says so on the page.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, asdict
from typing import Optional

import pandas as pd

from . import compliance, ai

# Indicative fine bands in DZD by finding area, for prioritisation only.
# (low, high). Coverage is an operational risk, not a statutory fine.
FINE_BANDS = {
    "Minimum wage": (30_000, 100_000),
    "Overtime":     (20_000, 60_000),
    "Contracts":    (20_000, 50_000),
    "Leave":        (10_000, 30_000),
    "Coverage":     (0, 0),
}
_LIKELIHOOD = {"critical": "Probable", "warning": "Possible", "info": "Faible"}
_SEVERITY_FR = {"critical": "CRITIQUE", "warning": "AVERTISSEMENT", "info": "INFO"}


@dataclass
class Finding:
    severity: str
    area: str
    message: str
    article: str
    fix: str
    fine_low: int
    fine_high: int
    likelihood: str

    def as_row(self) -> dict:
        band = "-" if self.fine_high == 0 else f"{self.fine_low:,} - {self.fine_high:,} DZD"
        return {
            "Severity": _SEVERITY_FR.get(self.severity, self.severity.upper()),
            "Violation": self.message,
            "Legal basis": self.article,
            "Est. fine exposure": band,
            "Catch likelihood": self.likelihood,
            "Fix": self.fix,
        }


def _to_finding(alert) -> Finding:
    low, high = FINE_BANDS.get(alert.category, (10_000, 30_000))
    return Finding(
        severity=alert.severity,
        area=alert.category,
        message=alert.message,
        article=alert.rule,
        fix=alert.action,
        fine_low=low,
        fine_high=high,
        likelihood=_LIKELIHOOD.get(alert.severity, "Possible"),
    )


def audit(roster=None, people=None, constraints=None, as_of: Optional[_dt.date] = None) -> dict:
    """Run the mock inspection and return findings + exposure + a risk score."""
    alerts = compliance.scan(roster=roster, people=people,
                             constraints=constraints, as_of=as_of)
    findings = [_to_finding(a) for a in alerts]
    card = compliance.scorecard(alerts)

    exposure_low = sum(f.fine_low for f in findings)
    exposure_high = sum(f.fine_high for f in findings)

    # A 0..100 "inspection risk" score: critical findings dominate.
    score = min(100, card["critical"] * 28 + card["warning"] * 10)
    if score >= 55:
        verdict = ("critical", "Exposition élevée , à corriger avant toute inspection")
    elif score >= 20:
        verdict = ("warning", "Exposition modérée , planifier des corrections")
    elif findings:
        verdict = ("warning", "Points mineurs à régulariser")
    else:
        verdict = ("ok", "Passerait probablement une inspection aujourd'hui")

    return {
        "findings": findings,
        "scorecard": card,
        "score": score,
        "status": verdict[0],
        "label": verdict[1],
        "exposure_low": exposure_low,
        "exposure_high": exposure_high,
    }


def to_frame(findings) -> pd.DataFrame:
    if not findings:
        return pd.DataFrame(columns=["Severity", "Violation", "Legal basis",
                                     "Est. fine exposure", "Catch likelihood", "Fix"])
    return pd.DataFrame([f.as_row() for f in findings])


def report(result: dict, lang: str = "en") -> str:
    """AI-written inspection report, grounded strictly in the findings."""
    findings = result["findings"]
    if not findings:
        return ("No violations detected in this run. Keep the roster, contracts "
                "and payroll as they are, and re-run the simulation after any "
                "change to staffing or pay.")

    facts = [
        {"severity": f.severity, "violation": f.message,
         "legal_basis": f.article, "fix": f.fix,
         "fine_band_dzd": [f.fine_low, f.fine_high]}
        for f in findings
    ]
    lang_name = "French" if lang == "fr" else "English"
    system = (
        "You simulate an Algerian labour inspector (inspecteur du travail) writing "
        "a short inspection report for the employer. Use ONLY the findings you are "
        "given - never invent a violation or a law. Be firm, specific and practical. "
        f"Write in {lang_name}."
    )
    user = (
        f"Inspection risk score: {result['score']}/100 ({result['label']}). "
        f"Estimated fine exposure: {result['exposure_low']:,} to "
        f"{result['exposure_high']:,} DZD. Findings (JSON):\n{facts}\n\n"
        "Write: (1) a two-sentence verdict, (2) the violations in priority order "
        "with the article and what must change, (3) the single cheapest fix to do "
        "first. Keep it under 220 words."
    )
    r = ai.chat(system, user, max_tokens=650, temperature=0.3)
    if r.ok and r.text.strip():
        return r.text.strip()
    return _template_report(result, lang)


def _template_report(result: dict, lang: str = "fr") -> str:
    if lang == "en":
        lines = [f"Inspection risk {result['score']}/100 - {result['label']}.",
                 f"Estimated exposure {result['exposure_low']:,} to {result['exposure_high']:,} DZD.", ""]
        for i, f in enumerate(result["findings"], 1):
            lines.append(f"{i}. [{f.severity.upper()}] {f.message}")
            lines.append(f"   Basis: {f.article}")
            lines.append(f"   Fix: {f.fix}")
        return "\n".join(lines)
    lines = [f"Risque d'inspection {result['score']}/100 , {result['label']}.",
             f"Exposition estimée : {result['exposure_low']:,} à {result['exposure_high']:,} DZD.", ""]
    for i, f in enumerate(result["findings"], 1):
        lines.append(f"{i}. [{_SEVERITY_FR.get(f.severity, f.severity.upper())}] {f.message}")
        lines.append(f"   Base : {f.article}")
        lines.append(f"   Correction : {f.fix}")
    return "\n".join(lines)


if __name__ == "__main__":
    from . import hr, labour_dz
    print("Inspection simulator - self check\n")
    people = hr.sample_workforce("sorter", 30, "Alger")
    # Inject a violation: push one below SNMG by faking a role gross is hard;
    # instead run on people + no roster (workforce-only checks).
    res = audit(roster=None, people=people, constraints=None)
    print("score:", res["score"], res["label"])
    print("findings:", len(res["findings"]))
    print(to_frame(res["findings"]).to_string(index=False)[:800])
    print("\nreport (template, no key):\n", _template_report(res, "en")[:400])
