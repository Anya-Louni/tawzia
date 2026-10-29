"""
tawzia_mcp/server.py
--------------------
Tawzia public MCP server: Algerian payroll and labour-law tools, usable from
any MCP client.

The tools calculate and cite the rule; they write nothing. They import the same
modules as the app (core/payroll_dz, core/legal, core/filings), so a rule changed
in config/dz_payroll_<year>.toml changes everywhere at once.

No tool approves, files, sends, pays, deletes or rejects: those actions stay in
the app, behind a human click.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server import MCPServer  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

from core import (calendar_dz, deadlines_dz, filings, law_corpus, legal,  # noqa: E402
                  payroll_dz)

mcp = MCPServer(
    "tawzia_mcp",
    instructions=(
        "Public Algerian payroll and labour-law tools (Tawzia). Every result "
        "cites the article and the rules version applied. Values marked [verify] "
        "come from a single or conflicting source: confirm them before a real "
        "payroll run."
    ),
)

PUBLIC = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                         idempotentHint=True, openWorldHint=False)
VERSION = payroll_dz.CONFIG_VERSION


class Fmt(str, Enum):
    markdown = "markdown"
    json = "json"


class _In(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    response_format: Fmt = Field(Fmt.markdown, description="'markdown' (lisible) ou 'json' (machine).")


def _out(data: dict, fmt: Fmt, md: str) -> str:
    if fmt == Fmt.json:
        return json.dumps(data, ensure_ascii=False, default=str, indent=2)
    return md + f"\n\n_Rules: {VERSION}_"


def _n(v) -> str:
    return f"{v:,.0f}".replace(",", " ")


# ---------------------------------------------------------------------------
# Paie
# ---------------------------------------------------------------------------

class NetSalaryIn(_In):
    gross: Optional[float] = Field(None, ge=0, le=10_000_000,
                                   description="Brut mensuel en DA, s'il n'y a qu'une ligne de base. Ex. 60000")
    items: Optional[dict[str, float]] = Field(
        None, description="Lignes de paie {code: montant}. Codes : "
                          + ", ".join(payroll_dz.PAY_ITEMS) + ". Ex. {'base': 40000, 'panier': 3000}")
    worker_status: str = Field("standard", description="'standard', 'disabled' or 'retired'.")
    period: Optional[str] = Field(None, description="Month concerned, 'YYYY-MM'. Informational.")

    @field_validator("worker_status")
    @classmethod
    def _status(cls, v):
        if v not in payroll_dz.WORKER_STATUSES:
            raise ValueError(f"worker_status doit valoir {payroll_dz.WORKER_STATUSES}")
        return v


def _items(gross, items) -> dict:
    if items:
        return items
    if gross is None:
        raise ValueError("Donnez 'gross' ou 'items'.")
    return {"base": gross}


@mcp.tool(name="tawzia_calculate_net_salary", annotations=PUBLIC)
def calculate_net_salary(params: NetSalaryIn) -> str:
    """Algerian net salary from gross or pay lines: CNAS 9%, taxable base, IRG
    step by step (art. 104 scale, bounded 40% abatement, smoothing), net.
    Chaque ligne porte ses propres drapeaux CNAS / IRG."""
    try:
        b = payroll_dz.pay_breakdown(_items(params.gross, params.items), params.worker_status)
    except ValueError as e:
        return f"Erreur : {e}"
    s = b["irg_steps"]
    md = (f"**Net pay: {_n(b['net'])} DA**\n\n"
          f"| Step | DA |\n|---|---|\n| Gross | {_n(b['gross'])} |\n"
          f"| CNAS base | {_n(b['cnas_base'])} |\n| CNAS employee 9% | −{_n(b['cnas_employee'])} |\n"
          f"| Taxable base | {_n(b['taxable'])} |\n| IRG scale | {_n(s['bareme'])} |\n"
          f"| Abattement | −{_n(s['abatement'])} |\n| Lissage | {s['smoothing']} |\n"
          f"| IRG retenu | {_n(b['irg'])} |\n\n"
          + ("Taxable base at or below 30,000 DA: IRG exempt.\n\n" if s["exempt"] else "")
          + "Sources : " + " ; ".join(b["sources"]))
    return _out(b, params.response_format, md)


class EmployerCostIn(_In):
    gross: Optional[float] = Field(None, ge=0, le=10_000_000, description="Monthly gross per employee, DA.")
    items: Optional[dict[str, float]] = Field(None, description="Lignes de paie {code: montant}.")
    headcount: int = Field(1, ge=1, le=100_000, description="Number of employees at this salary.")


@mcp.tool(name="tawzia_calculate_employer_cost", annotations=PUBLIC)
def calculate_employer_cost(params: EmployerCostIn) -> str:
    """Employer cost: CNAS employer share by branch and total cost, for one or
    more employees. The scale comes from the dated configuration [verify]."""
    try:
        b = payroll_dz.pay_breakdown(_items(params.gross, params.items))
    except ValueError as e:
        return f"Erreur : {e}"
    k = params.headcount
    data = {"per_employee": {"gross": b["gross"], "employer_cnas": b["employer_cnas"],
                             "employer_cost": b["employer_cost"],
                             "employer_by_branch": b["employer_by_branch"]},
            "headcount": k, "total_employer_cost": b["employer_cost"] * k,
            "config_version": VERSION}
    rows = "".join(f"| {br} | {_n(v)} |\n" for br, v in b["employer_by_branch"].items())
    md = (f"**Employer cost: {_n(b['employer_cost'])} DA per employee, "
          f"{_n(b['employer_cost'] * k)} DA pour {k}.**\n\n| Branche CNAS (patronal) | DA |\n"
          f"|---|---|\n{rows}| **Total patronal** | **{_n(b['employer_cnas'])}** |\n\n"
          "Per-branch scale [verify: some sources give 26% in total].")
    return _out(data, params.response_format, md)


# ---------------------------------------------------------------------------
# Temps de travail
# ---------------------------------------------------------------------------

class OvertimeIn(_In):
    hours_per_day: list[float] = Field(..., min_length=7, max_length=7,
                                       description="Hours worked over 7 days. E.g. [8,8,8,8,8,8,0]")
    hourly_wage: float = Field(..., gt=0, le=100_000, description="Salaire horaire normal, DA.")
    contract_hours: Optional[float] = Field(None, gt=0, le=60, description="Contractual weekly hours (default 40).")


@mcp.tool(name="tawzia_check_overtime", annotations=PUBLIC)
def check_overtime(params: OvertimeIn) -> str:
    """Is a week legal? Overtime against the 20% cap (art. 31),
    majoration minimale due de 50 % (art. 32), repos hebdomadaire (art. 33)."""
    try:
        r = legal.check_overtime(params.hours_per_day, params.hourly_wage, params.contract_hours)
    except ValueError as e:
        return f"Erreur : {e}"
    v = "".join(f"- {x['article']} : {x['detail']}\n" for x in r["violations"]) or "- aucune\n"
    md = (f"**{'Legal' if r['legal'] else 'Illegal'}** · {r['total_hours']:.1f} h dont "
          f"{r['overtime_hours']:.1f} h sup. ({r['cap_used_pct']:.0f} % du plafond de "
          f"{r['cap_hours']:.0f} h)\n\nMajoration minimale due : {_n(r['min_premium_due'])} DA\n\n"
          f"Infractions :\n{v}\nSources : " + " ; ".join(r["sources"]))
    return _out(r, params.response_format, md)


class ShiftIn(_In):
    start: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Start 'HH:MM'. E.g. '22:00'")
    end: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Fin 'HH:MM'. Ex. '06:00'")
    worker_age: int = Field(..., ge=14, le=80)
    worker_gender: str = Field(..., pattern="^(F|M)$", description="'F' ou 'M'.")
    site_women_night_derogation: bool = Field(False, description="Does the site hold the inspector's exemption (art. 29)?")
    on_weekly_rest_day: bool = Field(False, description="Le shift tombe-t-il sur le repos hebdomadaire ?")
    compensatory_rest_planned: bool = Field(False, description="Is equal compensatory rest planned (art. 36)?")


@mcp.tool(name="tawzia_check_shift_legality", annotations=PUBLIC)
def check_shift_legality(params: ShiftIn) -> str:
    """Is a shift legal for this person? Night 21:00 to 05:00 (art. 27), under 19
    (art. 28), women and exemption (art. 29), rest (art. 33, 36)."""
    h = lambda s: _dt.time(*map(int, s.split(":")))  # noqa: E731
    try:
        r = legal.check_shift(h(params.start), h(params.end), worker_age=params.worker_age,
                              worker_gender=params.worker_gender,
                              site_women_night_derogation=params.site_women_night_derogation,
                              on_weekly_rest_day=params.on_weekly_rest_day,
                              compensatory_rest_planned=params.compensatory_rest_planned)
    except ValueError as e:
        return f"Erreur : {e}"
    v = "".join(f"- {x['article']} : {x['detail']}\n" for x in r["violations"]) or "- aucune\n"
    md = (f"**{'Legal' if r['legal'] else 'Not allowed'}** · shift "
          f"{'de nuit' if r['night'] else 'de jour'} (nuit : {r['night_window']})\n\n{v}")
    return _out(r, params.response_format, md)


class CddIn(_In):
    reason: str = Field(..., description="Motif : " + ", ".join(legal.CDD_CASES) + ", ou autre.")
    start: _dt.date
    end: _dt.date
    renewals: int = Field(0, ge=0, le=50)


@mcp.tool(name="tawzia_check_cdd_validity", annotations=PUBLIC)
def check_cdd_validity(params: CddIn) -> str:
    """Un CDD est-il permis ? Seuls les cas de l'art. 12 de la loi 90-11 l'autorisent."""
    try:
        r = legal.check_cdd(params.reason, params.start, params.end, params.renewals)
    except ValueError as e:
        return f"Erreur : {e}"
    md = (f"**{'Valable' if r['valid'] else 'Non valable'}** · {r['case']} · "
          f"{r['duration_months']} mois\n\n{r['explanation']}\n\n"
          + "".join(f"- {n}\n" for n in r["notes"]) + "\nSource : Loi 90-11, art. 12")
    return _out(r, params.response_format, md)


# ---------------------------------------------------------------------------
# Calendrier
# ---------------------------------------------------------------------------

class CalendarIn(_In):
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="Mois 'AAAA-MM'. Ex. '2026-11'")
    headcount: int = Field(..., ge=1, le=100_000, description="Headcount (decides monthly or quarterly CNAS).")
    tax_regime: str = Field("reel", description="'reel' or 'ifu'. Online filing on Jibaya'tic is mandatory under the real regime since 2026.")


@mcp.tool(name="tawzia_get_compliance_calendar", annotations=PUBLIC)
def get_compliance_calendar(params: CalendarIn) -> str:
    """A month's social and tax deadlines (G50, CNAS, DAS), moved to the next
    working day when needed, with portal and source."""
    y, m = map(int, params.month.split("-"))
    start = _dt.date(y, m, 1)
    items = deadlines_dz.upcoming(start, headcount=params.headcount, horizon_days=62)
    rows = []
    for o in items:
        due = filings.next_working_day(o.due)
        if (due.year, due.month) == (y, m):
            rows.append({"label": o.label, "body": o.body, "due": due.isoformat(),
                         "period": o.period, "portal": o.portal, "source": o.source,
                         "verify": o.confidence != "sourcee"})
    data = {"month": params.month, "headcount": params.headcount, "deadlines": rows,
            "config_version": VERSION}
    md = (f"**Deadlines for {params.month}** ({params.headcount} employees)\n\n"
          + ("".join(f"- {r['due']} · {r['label']} ({r['body']}), {r['period']}"
                     f"{' [verify]' if r['verify'] else ''} · {r['portal']}\n" for r in rows)
             or "No deadline this month.\n"))
    return _out(data, params.response_format, md)


class HolidaysIn(_In):
    year: int = Field(..., ge=2000, le=2100)


@mcp.tool(name="tawzia_get_public_holidays", annotations=PUBLIC)
def get_public_holidays(params: HolidaysIn) -> str:
    """Algerian public holidays for a year: fixed ones, and Hijri ones estimated by
    calculation (the exact date follows the official crescent-sighting announcement)."""
    y = params.year
    rows = [{"date": _dt.date(y, m, d).isoformat(), "name": n, "kind": "fixe"}
            for (m, d), n in calendar_dz.CIVIL_HOLIDAYS.items()]
    # Le 19 juin figure dans la liste du brief mais pas encore dans le moteur.
    rows.append({"date": _dt.date(y, 6, 19).isoformat(), "name": "19 June", "kind": "fixed [verify]"})
    for hy in (y - 579, y - 578, y - 577):
        for (hm, hd), n in calendar_dz.HIJRI_HOLIDAYS.items():
            try:
                d = calendar_dz.from_hijri(hy, hm, hd)
            except ValueError:
                continue
            if d.year == y:
                rows.append({"date": d.isoformat(), "name": n, "kind": "Hijri, estimated"})
    rows.sort(key=lambda r: r["date"])
    data = {"year": y, "holidays": rows,
            "note": "Hijri dates are confirmed by official announcement, within one day."}
    md = (f"**Public holidays {y}**\n\n" + "".join(f"- {r['date']} · {r['name']} ({r['kind']})\n" for r in rows)
          + f"\n{data['note']}")
    return _out(data, params.response_format, md)


# ---------------------------------------------------------------------------
# Textes
# ---------------------------------------------------------------------------

class LawSearchIn(_In):
    query: str = Field(..., min_length=2, max_length=200, description="Question or keywords. E.g. 'night work for women'")
    limit: int = Field(5, ge=1, le=20)


@mcp.tool(name="tawzia_search_labour_law", annotations=PUBLIC)
def search_labour_law(params: LawSearchIn) -> str:
    """Search the corpus of applied articles (Law 90-11, Ord. 97-03, Law 20-03,
    Law 25-11). Returns summaries with a link to the text, never an
    interpretation. Nothing found: the question is for a lawyer."""
    hits = law_corpus.search(params.query, params.limit)
    data = {"query": params.query, "count": len(hits), "articles": hits}
    md = ("".join(f"**{h['text']} {h['article']}, {h['title']}**\n{h['summary']}\n[texte]({h['url']})\n\n"
                  for h in hits)
          or "No article in the corpus answers this. Ask a lawyer or HR.")
    return _out(data, params.response_format, md + "\n_Summaries, not the official text._")


_LINES = {
    "base": ("Salaire de base", "الأجر القاعدي", "Base salary",
             "The pay for the role, before bonuses."),
    "cnas": ("Retenue CNAS", "اقتطاع الضمان الاجتماعي", "Social security (CNAS)",
             "9% of the contribution base, the employee share of social security."),
    "taxable": ("Base imposable", "الوعاء الخاضع للضريبة", "Taxable base",
                "Gross subject to IRG, minus the CNAS deduction."),
    "irg": ("IRG", "الضريبة على الدخل الإجمالي", "Income tax (IRG)",
            "Tax withheld at source: scale, bounded 40% abatement, smoothing, "
            "exemption up to 30,000 DA taxable."),
    "net": ("Net à payer", "الصافي للدفع", "Net pay", "What the employee receives."),
    "heures_sup": ("Heures supplémentaires", "الساعات الإضافية", "Overtime",
                   "Hours beyond legal working time, paid at least 50% extra (art. 32)."),
}


class PayslipLineIn(_In):
    line_code: str = Field(..., description="Code: " + ", ".join(_LINES))


@mcp.tool(name="tawzia_explain_payslip_line", annotations=PUBLIC)
def explain_payslip_line(params: PayslipLineIn) -> str:
    """Explain a payslip line in French, Arabic and English."""
    row = _LINES.get(params.line_code.lower())
    if not row:
        return f"Error: unknown code. Valid codes: {', '.join(_LINES)}"
    fr, ar, en, why = row
    data = {"code": params.line_code, "fr": fr, "ar": ar, "en": en, "explanation": why}
    return _out(data, params.response_format, f"**{fr}** · {ar} · {en}\n\n{why}")


class PdfIn(_In):
    pdf_base64: str = Field(..., min_length=10, max_length=28_000_000,
                            description="The PDF file, base64-encoded (20 MB max).")
    filename: str = Field("document.pdf", max_length=200)
    chunk_tokens: int = Field(800, ge=100, le=4000, description="Target chunk size in tokens.")
    overlap_tokens: int = Field(80, ge=0, le=500)
    include_chunks: bool = Field(True, description="Return the chunks as well as the Markdown.")


@mcp.tool(name="tawzia_pdf_to_text", annotations=PUBLIC)
def pdf_to_text(params: PdfIn) -> str:
    """Turn a PDF into AI-readable text: clean Markdown with page markers and
    headings, plus paragraph-aligned chunks that cite their pages. Scanned pages
    with no text layer are listed, never guessed. Nothing is stored."""
    import base64
    import binascii
    from core import pdf_ingest
    try:
        data = base64.b64decode(params.pdf_base64, validate=True)
        r = pdf_ingest.convert(data, params.filename, chunk_tokens=params.chunk_tokens,
                               overlap_tokens=params.overlap_tokens)
    except (binascii.Error, ValueError) as e:
        return f"Erreur : {e}"
    data_out = {"source": r["source"], "stats": r["stats"], "scanned_pages": r["scanned_pages"],
                "metadata": r["metadata"], "markdown": r["markdown"]}
    if params.include_chunks:
        data_out["chunks"] = r["chunks"]
    md = (f"**{r['source']}** · {r['stats']['pages']} pages · ~{r['stats']['tokens_est']} tokens · "
          f"{r['stats']['chunks']} chunks"
          + (f"\n\nScanned pages (OCR needed): {r['scanned_pages']}" if r["scanned_pages"] else "")
          + "\n\n" + r["markdown"])
    return _out(data_out, params.response_format, md)


# shortcut: no rate limiting yet on the public HTTP endpoint; add a reverse-proxy
# limit (or server middleware) before exposing it publicly.
if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http", port=8765, stateless_http=True, json_response=True)
    else:
        mcp.run()
