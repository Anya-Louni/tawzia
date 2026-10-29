"""
core/copilot.py
---------------
The assistant's decision engine: it learns from the company's own database.

The manager asks "should we hire?", "who might leave?", "are we compliant?",
and it answers grounded in this company's own numbers, then recommends.

How it "learns from the company's database": it never free-associates. On every
question it first builds a factual brief from the company's data through the
owned engines (KPIs, anomalies, attrition, the real cost stack), all read via
core/company_data, so on an imported file the brief is the customer's real
figures. That brief is handed to the language layer as the ONLY source of
truth, with a strict instruction to reason only from it and cite the numbers.

Without an AI key it still works: it returns the brief plus a deterministic,
rule-based recommendation.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from . import ai, anomalies as anom_mod, attrition as attr_mod, kpis as kpi_mod


def build_brief(people: list, records: list, as_of: Optional[_dt.date] = None,
                source_label: str = "") -> dict:
    """Everything the copilot is allowed to reason from, computed locally."""
    as_of = as_of or _dt.date.today()
    kres = kpi_mod.compute(people, records, as_of)
    ares = anom_mod.detect(people, records, as_of)
    risk_df = kres["extras"].get("risk_frame")

    kpis = {k.key: {"label": k.label, "value": round(float(k.value), 2),
                    "display": k.display, "band": k.band} for k in kres["kpis"]}

    top_anoms = [{
        "severity": anom_mod.SEVERITY_LABEL.get(a.severity, a.severity),
        "area": anom_mod.DOMAIN_LABEL.get(a.domain, a.domain),
        "employee": a.name, "finding": a.detail, "action": a.recommendation,
    } for a in ares["anomalies"][:8]]

    top_risk = []
    if risk_df is not None and not risk_df.empty:
        for _, r in risk_df.head(5).iterrows():
            top_risk.append({
                "employee": r["Name"], "risk_pct": r["Risk %"],
                "driver": r["Top driver"],
                "replacement_cost": int(r["Replacement cost (DZD)"]),
            })

    return {
        "source": source_label or "demo",
        "date": as_of.isoformat(),
        "headcount": len(people),
        "kpis": kpis,
        "anomalies": {"total": ares["summary"]["total"],
                      "critical": ares["summary"]["critique"],
                      "high": ares["summary"]["élevée"],
                      "top": top_anoms},
        "leaving_risk": {"summary": attr_mod.summary(risk_df) if risk_df is not None else {},
                         "top": top_risk},
    }


def brief_as_text(brief: dict) -> str:
    """Compact human/LLM-readable rendering of the brief."""
    lines = [f"DATA SOURCE: {brief['source']} · {brief['headcount']} employees "
             f"· as of {brief['date']}", "", "KEY INDICATORS:"]
    for k in brief["kpis"].values():
        lines.append(f"  - {k['label']}: {k['display']} [{k['band']}]")
    a = brief["anomalies"]
    lines += ["", f"ANOMALIES: {a['total']} in total "
                  f"({a['critical']} critical, {a['high']} high)"]
    for x in a["top"]:
        lines.append(f"  - [{x['severity']}] {x['area']} · {x['employee']}: {x['finding']}")
    r = brief["leaving_risk"]
    if r["top"]:
        lines += ["", "LEAVING RISK (top):"]
        for x in r["top"]:
            lines.append(f"  - {x['employee']}: {x['risk_pct']}% ({x['driver']}), "
                         f"replacement {x['replacement_cost']:,} DZD")
    return "\n".join(lines)


def rule_recommendation(brief: dict) -> list:
    """Concrete moves derived from the brief alone, ranked by urgency."""
    recs = []
    a = brief["anomalies"]
    if a["critical"]:
        recs.append(f":material/error: {a['critical']} critical payroll anomaly(ies) "
                    f"to fix first (see Anomaly detection).")
    kpis = brief["kpis"]

    def band_of(key):
        return kpis.get(key, {}).get("band")

    if band_of("absenteeism") in ("surveiller", "critique"):
        recs.append(f":material/event_busy: Absenteeism "
                    f"{kpis['absenteeism']['display']}: bringing it to 4% frees "
                    f"{kpis.get('absence_cost', {}).get('display', 'budget')} "
                    f"(model it in the Scenario simulator).")
    if band_of("attrition_risk") in ("surveiller", "critique"):
        n_high = kpis.get("high_risk", {}).get("display", "several")
        recs.append(f":material/trending_down: High leaving risk: {n_high} "
                    f"employee(s) at high risk. Hold retention talks this week.")
    if band_of("cdd_pct") == "critique":
        recs.append(f":material/badge: CDD share {kpis['cdd_pct']['display']}: "
                    f"moving your best people to CDI cuts turnover.")
    for x in brief["leaving_risk"].get("top", [])[:1]:
        recs.append(f":material/priority_high: Talk to {x['employee']} "
                    f"({x['risk_pct']}% risk, {x['driver'].lower()}).")
    if not recs:
        recs.append(":material/check_circle: No critical signal: indicators are "
                    "within norms. Keep the weekly review.")
    return recs


_SYSTEM = (
    "You are Tawzia's HR decision copilot for an Algerian employer. Reason ONLY "
    "from the BRIEF provided (the company's real figures, computed by the in-house "
    "models). Invent no figure: if data is missing, say so. Cite the brief's "
    "indicators to justify each point. Algerian context: SNMG, CNAS, IRG, labour "
    "law. Answer in English, concise and actionable. Structure: (1) direct answer, "
    "(2) what the figures say, (3) a concrete recommendation, and where relevant "
    "(4) the scenario to simulate to cost it."
)


def ask(question: str, brief: dict, max_tokens: int = 800) -> dict:
    """Answer a manager's question, grounded in the company's brief."""
    rule_recs = rule_recommendation(brief)
    if not any(ai.providers_available().values()):
        return {
            "text": "", "grounded": True, "recommendations": rule_recs,
            "used_ai": False,
            "note": "No AI key: recommendations come from the rules. Add "
                    "GROQ_API_KEY for a written answer.",
        }

    user = (f"BRIEF (source of truth, reason only from this):\n"
            f"{brief_as_text(brief)}\n\nMANAGER'S QUESTION:\n{question}")
    res = ai.chat(_SYSTEM, user, max_tokens=max_tokens, temperature=0.25)
    if not res.ok:
        return {"text": "", "grounded": True, "recommendations": rule_recs,
                "used_ai": False, "note": res.error or "AI error."}
    return {"text": res.text, "grounded": True, "recommendations": rule_recs,
            "used_ai": True, "model": res.model}


SUGGESTED_QUESTIONS = [
    "What are the 3 most urgent risks this month?",
    "Should we hire, and for which role first?",
    "Are we compliant on payroll, CNAS and IRG?",
    "Who might leave and how do we keep them?",
    "Where can I cut costs without hurting service?",
]


# Routing: one conversation, three knowledge domains. Keyword-based on purpose:
# no network call, no latency, a choice you can explain and test. When in doubt
# it falls back to "decision", which carries the company indicators.

TOPICS = {
    "planning": "Scheduling and load",
    "rh": "People, payroll and labour law",
    "decision": "Indicators and decisions",
}

_ROUTER_KEYWORDS = {
    "planning": (
        "schedule", "roster", "forecast", "shift", "temp", "peak", "demand",
        "volume", "parcel", "passenger", "cover", "coverage", "weekend",
        "friday", "saturday", "weather", "season", "overtime",
        "planning", "prévision", "prevision", "charge", "intérim", "interim",
        "vendredi", "samedi", "météo", "heures supplémentaires",
    ),
    "rh": (
        "leave day", "annual leave", "on leave", "absence", "absent", "late", "salary", "payroll", "payslip",
        "cnas", "irg", "snmg", "contract", "cdd", "cdi", "law", "legal",
        "inspection", "inspector", "maternity", "sick", "resign", "notice",
        "hire", "dismiss", "filing", "contribution", "seniority", "bonus",
        "congé", "conge", "salaire", "paie", "bulletin", "contrat", "loi",
        "maladie", "démission", "embauche", "déclaration", "cotisation",
    ),
    "decision": (
        "should", "how much", "worth", "recruit", "saving", "kpi", "indicator",
        "leaving risk", "might leave", "turnover", "budget", "decision",
        "priority", "urgent", "reduce", "cut", "cost", "invest",
        "faut-il", "dois-je", "combien", "rentable", "recruter", "risque",
        "décision", "priorité", "réduire", "coût",
    ),
}

# Phrasings that announce a judgement call weigh double: "should we hire"
# contains "hire" (an HR word) but the question is a decision.
_INTENT_MARKERS = ("should we", "should i", "is it worth", "what should", "faut-il", "faut il", "dois-je", "que faire")


def route(question: str) -> str:
    """The domain to query for this question (a key of TOPICS)."""
    q = (question or "").lower()
    scores = {topic: sum(1 for kw in kws if kw in q)
              for topic, kws in _ROUTER_KEYWORDS.items()}
    scores["decision"] += 2 * sum(1 for m in _INTENT_MARKERS if m in q)
    best = max(scores.values())
    if best == 0:
        return "decision"
    for topic in ("planning", "rh", "decision"):
        if scores[topic] == best:
            return topic
    return "decision"


if __name__ == "__main__":
    from . import attendance as att_mod, hr

    print("Decision copilot, self check\n")
    people = hr.sample_workforce("sorter", 50, "Alger")
    records = att_mod.sample_attendance(people, days=20)
    brief = build_brief(people, records, source_label="demo (simulated)")
    print(brief_as_text(brief)[:900], "...\n")
    for r in rule_recommendation(brief):
        print("   ", r.split(": ", 1)[-1])

    cases = [
        ("How many people do we need next Friday?", "planning"),
        ("Which day depends most on temps?", "planning"),
        ("How many leave days does Amine have left?", "rh"),
        ("What will the CNAS bill be this month?", "rh"),
        ("Are we compliant with labour law?", "rh"),
        ("Should we hire this quarter?", "decision"),
        ("Who might leave and why?", "decision"),
        ("Hello", "decision"),
        ("Faut-il embaucher ce trimestre ?", "decision"),
    ]
    bad = [(q, e, route(q)) for q, e in cases if route(q) != e]
    for q, e, g in bad:
        print(f"  FAIL {q!r}: expected {e}, got {g}")
    assert not bad, bad
    print(f"\n{len(cases)}/{len(cases)} questions routed as expected")
