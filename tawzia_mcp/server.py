"""
tawzia_mcp/server.py
--------------------
Le serveur MCP de Tawzia : les outils publics de droit du travail et de paie
algériens, utilisables depuis the AI model ou tout client MCP.

Tous les outils de ce fichier sont publics, en lecture seule : ils calculent et
citent la règle, ils n'écrivent rien. Ils importent les mêmes modules que
l'application (core/payroll_dz, core/legal, core/filings, core/law_corpus), donc
une règle changée dans config/dz_payroll_<année>.toml change partout à la fois.

Aucun outil n'approuve, ne dépose, n'envoie, ne paie, ne supprime ni ne refuse :
ces gestes restent dans l'application, derrière un clic humain.

Lancer :
    venv/Scripts/python.exe -m tawzia_mcp.server             # stdio (Inspector, the AI model Desktop)
    venv/Scripts/python.exe -m tawzia_mcp.server --http      # Streamable HTTP, port 8765
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
        "Outils publics de paie et de droit du travail algériens (Tawzia). "
        "Chaque résultat cite l'article et la version des règles appliquées. "
        "Les valeurs marquées [à vérifier] viennent d'une source unique ou "
        "contradictoire : confirmez-les avant une paie réelle."
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
    return md + f"\n\n_Règles : {VERSION}_"


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
    worker_status: str = Field("standard", description="'standard', 'disabled' (handicapé) ou 'retired' (retraité).")
    period: Optional[str] = Field(None, description="Mois concerné, 'AAAA-MM'. Informatif.")

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
    """Salaire net algérien à partir du brut ou des lignes de paie : CNAS 9 %, base
    imposable, IRG pas à pas (barème art. 104, abattement 40 % borné, lissage), net.
    Chaque ligne porte ses propres drapeaux CNAS / IRG."""
    try:
        b = payroll_dz.pay_breakdown(_items(params.gross, params.items), params.worker_status)
    except ValueError as e:
        return f"Erreur : {e}"
    s = b["irg_steps"]
    md = (f"**Net à payer : {_n(b['net'])} DA**\n\n"
          f"| Étape | DA |\n|---|---|\n| Brut | {_n(b['gross'])} |\n"
          f"| Base CNAS | {_n(b['cnas_base'])} |\n| CNAS salarié 9 % | −{_n(b['cnas_employee'])} |\n"
          f"| Base imposable | {_n(b['taxable'])} |\n| IRG barème | {_n(s['bareme'])} |\n"
          f"| Abattement | −{_n(s['abatement'])} |\n| Lissage | {s['smoothing']} |\n"
          f"| IRG retenu | {_n(b['irg'])} |\n\n"
          + ("Base imposable ≤ 30 000 DA : exonération IRG.\n\n" if s["exempt"] else "")
          + "Sources : " + " ; ".join(b["sources"]))
    return _out(b, params.response_format, md)


class EmployerCostIn(_In):
    gross: Optional[float] = Field(None, ge=0, le=10_000_000, description="Brut mensuel par salarié, DA.")
    items: Optional[dict[str, float]] = Field(None, description="Lignes de paie {code: montant}.")
    headcount: int = Field(1, ge=1, le=100_000, description="Nombre de salariés à ce salaire.")


@mcp.tool(name="tawzia_calculate_employer_cost", annotations=PUBLIC)
def calculate_employer_cost(params: EmployerCostIn) -> str:
    """Coût employeur : CNAS patronale détaillée par branche, coût total, pour un ou
    plusieurs salariés. Le barème vient de la configuration datée [à vérifier]."""
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
    md = (f"**Coût employeur : {_n(b['employer_cost'])} DA par salarié, "
          f"{_n(b['employer_cost'] * k)} DA pour {k}.**\n\n| Branche CNAS (patronal) | DA |\n"
          f"|---|---|\n{rows}| **Total patronal** | **{_n(b['employer_cnas'])}** |\n\n"
          "Barème par branche [à vérifier : certaines sources donnent 26 % au total].")
    return _out(data, params.response_format, md)


# ---------------------------------------------------------------------------
# Temps de travail
# ---------------------------------------------------------------------------

class OvertimeIn(_In):
    hours_per_day: list[float] = Field(..., min_length=7, max_length=7,
                                       description="Heures travaillées sur 7 jours. Ex. [8,8,8,8,8,8,0]")
    hourly_wage: float = Field(..., gt=0, le=100_000, description="Salaire horaire normal, DA.")
    contract_hours: Optional[float] = Field(None, gt=0, le=60, description="Durée contractuelle hebdo (défaut : 40 h).")


@mcp.tool(name="tawzia_check_overtime", annotations=PUBLIC)
def check_overtime(params: OvertimeIn) -> str:
    """Une semaine est-elle légale ? Heures sup. contre le plafond de 20 % (art. 31),
    majoration minimale due de 50 % (art. 32), repos hebdomadaire (art. 33)."""
    try:
        r = legal.check_overtime(params.hours_per_day, params.hourly_wage, params.contract_hours)
    except ValueError as e:
        return f"Erreur : {e}"
    v = "".join(f"- {x['article']} : {x['detail']}\n" for x in r["violations"]) or "- aucune\n"
    md = (f"**{'Légal' if r['legal'] else 'Illégal'}** · {r['total_hours']:.1f} h dont "
          f"{r['overtime_hours']:.1f} h sup. ({r['cap_used_pct']:.0f} % du plafond de "
          f"{r['cap_hours']:.0f} h)\n\nMajoration minimale due : {_n(r['min_premium_due'])} DA\n\n"
          f"Infractions :\n{v}\nSources : " + " ; ".join(r["sources"]))
    return _out(r, params.response_format, md)


class ShiftIn(_In):
    start: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Début 'HH:MM'. Ex. '22:00'")
    end: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Fin 'HH:MM'. Ex. '06:00'")
    worker_age: int = Field(..., ge=14, le=80)
    worker_gender: str = Field(..., pattern="^(F|M)$", description="'F' ou 'M'.")
    site_women_night_derogation: bool = Field(False, description="Le site a-t-il la dérogation de l'inspecteur (art. 29) ?")
    on_weekly_rest_day: bool = Field(False, description="Le shift tombe-t-il sur le repos hebdomadaire ?")
    compensatory_rest_planned: bool = Field(False, description="Un repos compensateur égal est-il prévu (art. 36) ?")


@mcp.tool(name="tawzia_check_shift_legality", annotations=PUBLIC)
def check_shift_legality(params: ShiftIn) -> str:
    """Un shift est-il légal pour cette personne ? Nuit 21 h à 5 h (art. 27), moins
    de 19 ans (art. 28), travailleuses et dérogation (art. 29), repos (art. 33, 36)."""
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
    md = (f"**{'Légal' if r['legal'] else 'Non autorisé'}** · shift "
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
    headcount: int = Field(..., ge=1, le=100_000, description="Effectif (décide CNAS mensuelle ou trimestrielle).")
    tax_regime: str = Field("reel", description="'reel' ou 'ifu'. Le dépôt en ligne Jibaya'tic est obligatoire au réel depuis 2026.")


@mcp.tool(name="tawzia_get_compliance_calendar", annotations=PUBLIC)
def get_compliance_calendar(params: CalendarIn) -> str:
    """Les échéances sociales et fiscales d'un mois (G50, CNAS, DAS), date limite
    reportée au jour ouvré suivant si besoin, avec portail et source."""
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
    md = (f"**Échéances de {params.month}** ({params.headcount} salariés)\n\n"
          + ("".join(f"- {r['due']} · {r['label']} ({r['body']}), {r['period']}"
                     f"{' [à vérifier]' if r['verify'] else ''} · {r['portal']}\n" for r in rows)
             or "Aucune échéance ce mois-ci.\n"))
    return _out(data, params.response_format, md)


class HolidaysIn(_In):
    year: int = Field(..., ge=2000, le=2100)


@mcp.tool(name="tawzia_get_public_holidays", annotations=PUBLIC)
def get_public_holidays(params: HolidaysIn) -> str:
    """Les jours fériés algériens d'une année : fixes, et hégiriens estimés par le
    calcul (la date exacte suit l'annonce officielle de l'observation du croissant)."""
    y = params.year
    rows = [{"date": _dt.date(y, m, d).isoformat(), "name": n, "kind": "fixe"}
            for (m, d), n in calendar_dz.CIVIL_HOLIDAYS.items()]
    # Le 19 juin figure dans la liste du brief mais pas encore dans le moteur.
    rows.append({"date": _dt.date(y, 6, 19).isoformat(), "name": "19 juin", "kind": "fixe [à vérifier]"})
    for hy in (y - 579, y - 578, y - 577):
        for (hm, hd), n in calendar_dz.HIJRI_HOLIDAYS.items():
            try:
                d = calendar_dz.from_hijri(hy, hm, hd)
            except ValueError:
                continue
            if d.year == y:
                rows.append({"date": d.isoformat(), "name": n, "kind": "hégirien, estimé"})
    rows.sort(key=lambda r: r["date"])
    data = {"year": y, "holidays": rows,
            "note": "Les dates hégiriennes sont confirmées par annonce officielle, à un jour près."}
    md = (f"**Jours fériés {y}**\n\n" + "".join(f"- {r['date']} · {r['name']} ({r['kind']})\n" for r in rows)
          + f"\n{data['note']}")
    return _out(data, params.response_format, md)


# ---------------------------------------------------------------------------
# Textes
# ---------------------------------------------------------------------------

class LawSearchIn(_In):
    query: str = Field(..., min_length=2, max_length=200, description="Question ou mots-clés. Ex. 'travail de nuit des femmes'")
    limit: int = Field(5, ge=1, le=20)


@mcp.tool(name="tawzia_search_labour_law", annotations=PUBLIC)
def search_labour_law(params: LawSearchIn) -> str:
    """Cherche dans le corpus des articles appliqués (loi 90-11, ord. 97-03, loi
    20-03, loi 25-11). Rend des résumés avec le lien du texte, jamais une
    interprétation. Rien trouvé : la question relève d'un juriste."""
    hits = law_corpus.search(params.query, params.limit)
    data = {"query": params.query, "count": len(hits), "articles": hits}
    md = ("".join(f"**{h['text']} {h['article']}, {h['title']}**\n{h['summary']}\n[texte]({h['url']})\n\n"
                  for h in hits)
          or "Aucun article du corpus ne répond. Posez la question à un juriste ou au service RH.")
    return _out(data, params.response_format, md + "\n_Résumés, pas le texte officiel._")


_LINES = {
    "base": ("Salaire de base", "الأجر القاعدي", "Base salary",
             "La rémunération du poste, avant primes."),
    "cnas": ("Retenue CNAS", "اقتطاع الضمان الاجتماعي", "Social security (CNAS)",
             "9 % de la base cotisable, part salariale de la sécurité sociale."),
    "taxable": ("Base imposable", "الوعاء الخاضع للضريبة", "Taxable base",
                "Brut soumis à l'IRG, moins la retenue CNAS."),
    "irg": ("IRG", "الضريبة على الدخل الإجمالي", "Income tax (IRG)",
            "Impôt retenu à la source : barème, abattement de 40 % borné, lissage, "
            "exonération jusqu'à 30 000 DA imposables."),
    "net": ("Net à payer", "الصافي للدفع", "Net pay", "Ce que le salarié reçoit."),
    "heures_sup": ("Heures supplémentaires", "الساعات الإضافية", "Overtime",
                   "Heures au-delà de la durée légale, majorées d'au moins 50 % (art. 32)."),
}


class PayslipLineIn(_In):
    line_code: str = Field(..., description="Code : " + ", ".join(_LINES))


@mcp.tool(name="tawzia_explain_payslip_line", annotations=PUBLIC)
def explain_payslip_line(params: PayslipLineIn) -> str:
    """Explique une ligne du bulletin de paie en français, arabe et anglais."""
    row = _LINES.get(params.line_code.lower())
    if not row:
        return f"Erreur : code inconnu. Codes possibles : {', '.join(_LINES)}"
    fr, ar, en, why = row
    data = {"code": params.line_code, "fr": fr, "ar": ar, "en": en, "explanation": why}
    return _out(data, params.response_format, f"**{fr}** · {ar} · {en}\n\n{why}")


# shortcut: no rate limiting yet on the public HTTP endpoint; add a reverse-proxy
# limit (or server middleware) before exposing it publicly.
if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http", port=8765, stateless_http=True, json_response=True)
    else:
        mcp.run()
