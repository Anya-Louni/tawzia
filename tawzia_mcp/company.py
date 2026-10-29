"""
tawzia_mcp/company.py
---------------------
The "company" MCP server: read a company's data and prepare drafts, from any
MCP client (brief, part B4).

Safety rule
===========
Tools read, calculate, or **create a card** in the decision inbox. None
approves, files, sends, pays, deletes or rejects: the decision stays in the
app, with a human.

Access
======
Over HTTP every request carries a Bearer token, checked by `DemoTokenVerifier`.
Demo tokens come from TAWZIA_MCP_TOKENS (JSON
{"token": {"client": "...", "scopes": ["company:DEMO", "role:hr"]}}). Without
that variable no token is valid: the server is closed by default.
shortcut: this is the resource-server half of OAuth 2.1 (token check, scopes);
the authorization server that issues tokens is not built yet; plug a real issuer
(Keycloak, Auth0, Entra) into `token_verifier` before any client data goes live.

Over stdio (local machine) the caller is the machine's user: the role comes
from TAWZIA_MCP_LOCAL_ROLE ("hr" by default).

Every call is written to the log (who, tool, argument fingerprint).

Run:
    venv/Scripts/python.exe -m tawzia_mcp.company            # stdio
    venv/Scripts/python.exe -m tawzia_mcp.company --http     # HTTP, port 8766
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server import MCPServer  # noqa: E402
from mcp.server.auth.middleware.auth_context import get_access_token  # noqa: E402
from mcp.server.auth.provider import AccessToken  # noqa: E402
from mcp.server.auth.settings import AuthSettings  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

from core import (attendance, bias, cv_screen, db, deadlines_dz, filings,  # noqa: E402
                  labour_dz, onboarding, payroll_dz, rules,
                  scheduler, seed_company as sc, self_service, talent)

PORT = 8766
COMPANY = "DEMO"


class DemoTokenVerifier:
    """Check a Bearer token against the TAWZIA_MCP_TOKENS table."""

    async def verify_token(self, token: str) -> AccessToken | None:
        table = json.loads(os.environ.get("TAWZIA_MCP_TOKENS", "{}") or "{}")
        info = table.get(token)
        if not info:
            return None
        return AccessToken(token=token, client_id=info["client"], scopes=info["scopes"],
                           resource=f"http://localhost:{PORT}/mcp")


mcp = MCPServer(
    "tawzia_company_mcp",
    instructions=("A Tawzia company's data, read-only, and drafts that wait "
                  "for human approval in the app."),
    token_verifier=DemoTokenVerifier(),
    auth=AuthSettings(issuer_url="http://localhost:8766",
                      resource_server_url=f"http://localhost:{PORT}/mcp",
                      required_scopes=[f"company:{COMPANY}"],
                      validate_token_resource=True),
)

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True,
                       openWorldHint=False)
DRAFT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False,
                        openWorldHint=False)


# ---------------------------------------------------------------------------
# Access, log, formatting
# ---------------------------------------------------------------------------

def _caller() -> tuple[str, str, set]:
    """(client, role, scopes). Over stdio, the local user."""
    tok = get_access_token()
    if tok is None:
        role = os.environ.get("TAWZIA_MCP_LOCAL_ROLE", "hr")
        return "local", role, {f"company:{COMPANY}", f"role:{role}", "cabinet"}
    scopes = set(tok.scopes)
    role = next((s.split(":", 1)[1] for s in scopes if s.startswith("role:")), "auditor")
    return tok.client_id, role, scopes


def _guard(tool: str, args: dict, roles: tuple = ("hr", "payroll", "auditor")) -> tuple:
    client, role, scopes = _caller()
    if f"company:{COMPANY}" not in scopes:
        raise PermissionError("This token does not give access to this company.")
    if role not in roles:
        raise PermissionError(f"The role \"{role}\" cannot use {tool}.")
    digest = hashlib.sha256(json.dumps(args, sort_keys=True, default=str).encode()).hexdigest()[:12]
    con = db.seed(db.connect())
    db.log(con, client, role, f"mcp:{tool}", COMPANY, f"args {digest}")
    return con, client, role


class _In(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    response_format: str = Field("markdown", pattern="^(markdown|json)$")


class _Page(_In):
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


def _out(data, fmt: str, md: str) -> str:
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, default=str, indent=2)
    return md


def _page(items: list, p: _Page) -> dict:
    chunk = items[p.offset:p.offset + p.limit]
    return {"items": chunk, "total_count": len(items), "count": len(chunk),
            "offset": p.offset, "has_more": p.offset + len(chunk) < len(items),
            "next_offset": p.offset + len(chunk) if p.offset + len(chunk) < len(items) else None}


def _err(e: Exception) -> str:
    return f"Erreur : {e}"


def _people() -> list:
    return list(sc.people())


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

class ListEmployeesIn(_Page):
    site: Optional[str] = Field(None, description="Code de site : " + ", ".join(sc.SITES))
    contract: Optional[str] = Field(None, pattern="^(CDI|CDD)$")


@mcp.tool(name="tawzia_list_employees", annotations=READ)
def list_employees(params: ListEmployeesIn) -> str:
    """Paginated employee list: staff number, name, role, site, contract. No sensitive field."""
    try:
        _guard("list_employees", params.model_dump())
    except PermissionError as e:
        return _err(e)
    rows = [{"id": e.emp_id, "name": e.name, "role": labour_dz.ROLES[e.role_key].label,
             "site": e.site, "contract": e.contract, "hire_date": e.hire_date.isoformat()}
            for e in _people()
            if (not params.site or e.site == params.site)
            and (not params.contract or e.contract == params.contract)]
    pg = _page(rows, params)
    md = (f"**{pg['total_count']} employees** (showing {pg['offset'] + 1} to "
          f"{pg['offset'] + pg['count']})\n\n"
          + "".join(f"- {r['id']} · {r['name']} · {r['role']} · {r['site']} · {r['contract']}\n"
                    for r in pg["items"])
          + (f"\nSuite : offset={pg['next_offset']}" if pg["has_more"] else ""))
    return _out(pg, params.response_format, md)


class GetEmployeeIn(_In):
    employee_id: str = Field(..., description="Matricule. Ex. 'DH1000'")


@mcp.tool(name="tawzia_get_employee", annotations=READ)
def get_employee(params: GetEmployeeIn) -> str:
    """An employee's record, cut to what the token's role may see, with their
    leave balance. Masked sensitive fields read "masked"."""
    try:
        con, client, role = _guard("get_employee", params.model_dump())
        rec = db.get_employee(con, params.employee_id, actor=client, role=role, why="outil MCP")
    except PermissionError as e:
        return _err(e)
    if rec is None:
        return _err(ValueError(f"Matricule inconnu : {params.employee_id}. Utilisez tawzia_list_employees."))
    emp = next(e for e in _people() if e.emp_id == params.employee_id)
    rec["leave_balance_days"] = emp.accrued_leave(_dt.date.today())
    md = "\n".join(f"- **{k}** : {v}" for k, v in rec.items())
    return _out(rec, params.response_format, md)


class CardsIn(_Page):
    status: str = Field("pending", pattern="^(pending|approved|rejected|all)$")


@mcp.tool(name="tawzia_list_inbox_cards", annotations=READ)
def list_inbox_cards(params: CardsIn) -> str:
    """Decision-inbox cards created by the tools and onboarding."""
    try:
        con, *_ = _guard("list_inbox_cards", params.model_dump())
    except PermissionError as e:
        return _err(e)
    q = "SELECT id, source, agent, title, status, created FROM inbox_cards"
    rows = [dict(r) for r in (con.execute(q + " ORDER BY id") if params.status == "all"
                              else con.execute(q + " WHERE status = ? ORDER BY id", (params.status,)))]
    pg = _page(rows, params)
    md = "".join(f"- #{r['id']} [{r['status']}] {r['agent']} · {r['title']}\n" for r in pg["items"]) \
        or "Aucune carte."
    return _out(pg, params.response_format, md)


class MonthIn(_In):
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="'AAAA-MM'")


def _payroll_lines() -> list:
    h = rules.payroll()["hours"]
    cap = h["legal_week"] * h["overtime_cap_fraction"] * 52 / 12
    out = []
    for e in _people():
        b = payroll_dz.pay_breakdown({"base": round(e.monthly_gross())})
        flags = []
        if b["gross"] < labour_dz.SNMG_MONTHLY:
            flags.append("sous le SNMG")
        if e.overtime_hours_month > cap:
            flags.append(f"heures sup. {e.overtime_hours_month:.0f} h > {cap:.0f} h (art. 31)")
        out.append({"id": e.emp_id, "name": e.name, "gross": b["gross"], "irg": b["irg"],
                    "net": b["net"], "overtime_hours": e.overtime_hours_month, "flags": flags})
    return out


@mcp.tool(name="tawzia_preview_payroll", annotations=READ)
def preview_payroll(params: MonthIn) -> str:
    """Preview a month's payroll: totals, anomalies, lines. Calculates, saves nothing."""
    try:
        _guard("preview_payroll", params.model_dump(), roles=("hr", "payroll"))
    except PermissionError as e:
        return _err(e)
    lines = _payroll_lines()
    issues = [l for l in lines if l["flags"]]
    data = {"month": params.month, "employees": len(lines),
            "gross_total": sum(l["gross"] for l in lines),
            "net_total": sum(l["net"] for l in lines),
            "irg_total": sum(l["irg"] for l in lines), "anomalies": issues,
            "config_version": payroll_dz.CONFIG_VERSION, "lines": lines}
    md = (f"**Payroll {params.month}**: {len(lines)} employees, net {data['net_total']:,.0f} DA, "
          f"IRG {data['irg_total']:,.0f} DA, {len(issues)} anomalie(s)\n\n"
          + "".join(f"- {i['name']} : {', '.join(i['flags'])}\n" for i in issues))
    return _out(data, params.response_format, md)


class FilingIn(_In):
    type: str = Field(..., pattern="^(g50_irg|cnas_monthly|das)$")
    period: str = Field(..., description="'AAAA-MM' (G50, CNAS) ou 'AAAA' (DAS)")


@mcp.tool(name="tawzia_get_filing_draft", annotations=READ)
def get_filing_draft(params: FilingIn) -> str:
    """The costed draft of a filing (G50, CNAS, DAS) with deadline and portal.
    Draft only: filing happens on the portal, by a human."""
    try:
        _guard("get_filing_draft", params.model_dump(), roles=("hr", "payroll", "auditor"))
        ppl = _people()
        if params.type == "das":
            d = filings.das_draft(ppl, int(params.period[:4]))
        else:
            y, m = map(int, params.period.split("-"))
            d = (filings.g50_draft if params.type == "g50_irg" else filings.cnas_draft)(ppl, y, m)
    except (PermissionError, ValueError) as e:
        return _err(e)
    d = {k: v for k, v in d.items() if k != "lines"} | {"lines_count": len(d.get("lines", []))}
    md = "\n".join(f"- **{k}** : {v}" for k, v in d.items())
    return _out(d, params.response_format, md)


class ScheduleIn(_In):
    site: str = Field(..., description="Code de site : " + ", ".join(sc.SITES))
    week_start: Optional[_dt.date] = Field(None, description="Starting Saturday. Default: next week.")
    ramadan: bool = False


@mcp.tool(name="tawzia_get_schedule", annotations=READ)
def get_schedule(params: ScheduleIn) -> str:
    """A legal weekly schedule for a site (solved by CP-SAT, a few seconds)."""
    try:
        _guard("get_schedule", params.model_dump())
    except PermissionError as e:
        return _err(e)
    if params.site not in sc.SITES:
        return _err(ValueError(f"Site inconnu. Sites : {list(sc.SITES)}"))
    r = scheduler.solve(params.site, params.week_start or scheduler.next_week_start(),
                        ramadan=params.ramadan)
    data = {"status": r.status, "violations": r.violations, "overtime_hours": r.overtime_hours,
            "shortfall": sum(r.shortfall.values()), "blocked_nights": r.blocked_nights,
            "grid": scheduler.grid(r)}
    md = (f"**{r.status}** · {len(r.violations)} violation(s) · overtime {r.overtime_hours:.0f} h · "
          f"{data['shortfall']} uncovered shift(s) · {len(r.blocked_nights)} night(s) blocked "
          f"by law")
    return _out(data, params.response_format, md)


@mcp.tool(name="tawzia_list_open_positions", annotations=READ)
def list_open_positions(params: _Page) -> str:
    """Les postes ouverts au recrutement."""
    try:
        _guard("list_open_positions", params.model_dump())
    except PermissionError as e:
        return _err(e)
    rows = [{"role_key": k, "title": j.title, "min_education": j.min_education,
             "min_experience_years": j.min_experience_years} for k, j in cv_screen.JOBS.items()]
    pg = _page(rows, params)
    return _out(pg, params.response_format,
                "".join(f"- {r['role_key']} · {r['title']}\n" for r in pg["items"]))


class RankingIn(_Page):
    role_key: str = Field(..., description="Poste : " + ", ".join(cv_screen.JOBS))


@mcp.tool(name="tawzia_get_candidate_ranking", annotations=READ)
def get_candidate_ranking(params: RankingIn) -> str:
    """The applicant ranking for a role, with the reason for each rank and the
    fairness audit (four-fifths rule)."""
    try:
        _guard("get_candidate_ranking", params.model_dump(), roles=("hr",))
    except PermissionError as e:
        return _err(e)
    job = cv_screen.JOBS.get(params.role_key)
    if job is None:
        return _err(ValueError(f"Poste inconnu. Postes : {list(cv_screen.JOBS)}"))
    ranked = talent.rank_pool(talent.sample_pool(params.role_key, n=28), job)
    rows = [{"rank": i + 1, "name": s.candidate.name, "score": s.score, "band": s.band,
             "why": s.pluses[:2], "gaps": s.flags[:2]} for i, s in enumerate(ranked)]
    data = _page(rows, params) | {"bias_audit": bias.four_fifths(ranked)}
    md = ("".join(f"{r['rank']}. {r['name']} · {r['score']} % · {r['band']}\n" for r in data["items"])
          + f"\nFairness audit: {'no gap' if data['bias_audit']['ok'] else 'gap to review'}")
    return _out(data, params.response_format, md)


@mcp.tool(name="tawzia_get_onboarding_status", annotations=READ)
def get_onboarding_status(params: GetEmployeeIn) -> str:
    """Progress of an employee's onboarding: tasks, documents (present / verified /
    missing), probation end. Never a document's content."""
    try:
        con, *_ = _guard("get_onboarding_status", params.model_dump(), roles=("hr",))
    except PermissionError as e:
        return _err(e)
    tasks = [dict(r) for r in con.execute(
        "SELECT task, owner, due, status FROM onboarding_tasks WHERE employee_id = ?",
        (params.employee_id,))]
    docs = [dict(r) for r in con.execute(
        "SELECT kind, status FROM documents WHERE employee_id = ?", (params.employee_id,))]
    data = {"employee_id": params.employee_id, "tasks": tasks, "documents": docs,
            "open_tasks": sum(1 for t in tasks if t["status"] != "done")}
    md = (f"{len(tasks)} task(s), {data['open_tasks']} open; {len(docs)} document(s)."
          if tasks or docs else "No onboarding in progress for this staff number.")
    return _out(data, params.response_format, md)


class TrialIn(_Page):
    days_ahead: int = Field(60, ge=1, le=400)


@mcp.tool(name="tawzia_list_upcoming_trial_ends", annotations=READ)
def list_upcoming_trial_ends(params: TrialIn) -> str:
    """Probation periods ending in the next N days (art. 18)."""
    try:
        _guard("list_upcoming_trial_ends", params.model_dump(), roles=("hr",))
    except PermissionError as e:
        return _err(e)
    months = rules.payroll()["work_time"]["trial_max_months"]
    today = _dt.date.today()
    rows = []
    for e in _people():
        end = e.hire_date + _dt.timedelta(days=int(months * 30.44))
        if today <= end <= today + _dt.timedelta(days=params.days_ahead):
            rows.append({"id": e.emp_id, "name": e.name, "trial_end": end.isoformat()})
    pg = _page(sorted(rows, key=lambda r: r["trial_end"]), params)
    return _out(pg, params.response_format,
                "".join(f"- {r['trial_end']} · {r['name']}\n" for r in pg["items"]) or "Aucune.")


@mcp.tool(name="tawzia_list_client_companies", annotations=READ)
def list_client_companies(params: _Page) -> str:
    """For an accounting firm: its client companies, the next deadline and the
    open cards for each."""
    client, role, scopes = _caller()
    if "cabinet" not in scopes:
        return _err(PermissionError("Reserved for accounting-firm tokens (scope 'cabinet')."))
    con = db.seed(db.connect())
    db.log(con, client, role, "mcp:list_client_companies", "cabinet", "")
    nxt = deadlines_dz.next_critical(headcount=len(_people()))
    rows = [{"company": COMPANY, "name": sc.COMPANY["name"], "employees": len(_people()),
             "next_deadline": f"{nxt.label} {nxt.due}" if nxt else None,
             "open_cards": len(db.pending_cards(con))}]
    pg = _page(rows, params)
    return _out(pg, params.response_format,
                "".join(f"- {r['name']} · {r['employees']} employees · {r['next_deadline']} · "
                        f"{r['open_cards']} carte(s)\n" for r in pg["items"]))


# ---------------------------------------------------------------------------
# Drafts: each creates a card, nothing more
# ---------------------------------------------------------------------------

def _card(con, client, agent, title, detail, law, decision, payload=None) -> str:
    cid = db.add_card(con, source=f"mcp:{client}", agent=agent, title=title, detail=detail,
                      law=law, decision=decision, payload=payload)
    return json.dumps({"card_id": cid, "status": "pending",
                       "note": "En attente d'approbation humaine dans Tawzia."}, ensure_ascii=False)


class DocIn(_In):
    employee_id: str
    doc_type: str = Field("attestation_travail",
                          pattern="^(attestation_travail|attestation_salaire|certificat_travail)$")
    language: str = Field("fr_ar", pattern="^(fr|ar|fr_ar)$")


@mcp.tool(name="tawzia_draft_document", annotations=DRAFT)
def draft_document(params: DocIn) -> str:
    """Draft an attestation or certificate and put it on a "to sign" card."""
    try:
        con, client, _ = _guard("draft_document", params.model_dump(), roles=("hr",))
    except PermissionError as e:
        return _err(e)
    emp = next((e for e in _people() if e.emp_id == params.employee_id), None)
    if emp is None:
        return _err(ValueError("Matricule inconnu."))
    doc = self_service.attestation_text(emp, sc.COMPANY["name"], "Le responsable RH", _dt.date.today())
    return _card(con, client, "Guichet", f"{params.doc_type.replace('_', ' ').capitalize()} for {emp.name}: ready to sign",
                 "Drafted from the employee record.", "Facts from the employee record",
                 "Document signed and handed to the employee.", {"document": doc})


class ScheduleDraftIn(ScheduleIn):
    pass


@mcp.tool(name="tawzia_draft_schedule", annotations=DRAFT)
def draft_schedule(params: ScheduleDraftIn) -> str:
    """Calcule le planning d'une semaine et le met en carte de validation."""
    try:
        con, client, _ = _guard("draft_schedule", params.model_dump(), roles=("hr",))
    except PermissionError as e:
        return _err(e)
    ws = params.week_start or scheduler.next_week_start()
    r = scheduler.solve(params.site, ws, ramadan=params.ramadan)
    return _card(con, client, "Planning", f"Schedule for week of {ws:%d/%m}, site {params.site}: ready",
                 f"{len(r.violations)} violation(s), overtime {r.overtime_hours:.0f} h, "
                 f"{sum(r.shortfall.values())} uncovered shift(s).",
                 "Ord. 97-03 · Law 90-11 art. 27 to 33", "Schedule published to the teams.")


class LeaveIn(_In):
    request_id: str = Field(..., description="Identifiant de demande. Ex. 'R200'")
    suggestion: str = Field("approve", pattern="^(approve|reject)$")


@mcp.tool(name="tawzia_draft_leave_decision", annotations=DRAFT)
def draft_leave_decision(params: LeaveIn) -> str:
    """Prepare the answer to a leave request, with the legal check, as a card."""
    try:
        con, client, _ = _guard("draft_leave_decision", params.model_dump(), roles=("hr",))
    except PermissionError as e:
        return _err(e)
    ppl = _people()
    req = next((r for r in attendance.sample_requests(ppl) if r.req_id == params.request_id), None)
    if req is None:
        return _err(ValueError("Demande inconnue."))
    emp = next(e for e in ppl if e.emp_id == req.emp_id)
    d = attendance.decide_request(req, emp)
    return _card(con, client, "Présence", f"{req.kind_label} for {req.emp_name}: "
                 f"{'approval' if params.suggestion == 'approve' else 'refusal'} proposed",
                 " ".join(d["reasons"] + d["warnings"]), "Law 90-11, art. 39 to 54",
                 "Answer sent to the employee.")


class JobIn(_In):
    brief: str = Field(..., min_length=10, max_length=600, description="Le besoin en trois lignes.")
    role_key: str = Field("ramp_agent", description="Poste : " + ", ".join(labour_dz.ROLES))
    language: str = Field("fr", pattern="^(fr|ar)$")


@mcp.tool(name="tawzia_draft_job_post", annotations=DRAFT)
def draft_job_post(params: JobIn) -> str:
    """Draft a job post fitted to the workforce and Algerian law, as a card."""
    from core import job_post
    try:
        con, client, _ = _guard("draft_job_post", params.model_dump(), roles=("hr",))
    except PermissionError as e:
        return _err(e)
    post = job_post.draft(params.brief, job_post.pool_facts(_people(), params.role_key), use_ai=False)
    return _card(con, client, "Recrutement", f"Job post \"{post.title}\" ready to publish",
                 post.summary, "Law 04-19 as amended by Law 20-03 (ANEM filing)",
                 "Post filed with ANEM and published.", {"markdown": post.as_markdown()})


@mcp.tool(name="tawzia_draft_payroll_run", annotations=DRAFT)
def draft_payroll_run(params: MonthIn) -> str:
    """Prepare a month's payroll and put it on an approval card."""
    try:
        con, client, _ = _guard("draft_payroll_run", params.model_dump(), roles=("hr", "payroll"))
    except PermissionError as e:
        return _err(e)
    lines = _payroll_lines()
    issues = [l for l in lines if l["flags"]]
    return _card(con, client, "Paie", f"Payroll {params.month} ready: {len(lines)} employees, "
                 f"{len(issues)} item(s) to check",
                 "; ".join(f"{i['name']} : {', '.join(i['flags'])}" for i in issues) or "No discrepancy.",
                 "SNMG, CNAS, IRG art. 104, overtime art. 31",
                 "Payslips published, transfer and entries generated.")


class InviteIn(_In):
    candidate_name: str = Field(..., min_length=3, max_length=80)
    role_key: str = Field("ramp_agent")
    site: str = Field("ALG")
    start_date: _dt.date
    gender: str = Field("F", pattern="^(F|M)$")


@mcp.tool(name="tawzia_draft_registration_invite", annotations=DRAFT)
def draft_registration_invite(params: InviteIn) -> str:
    """Prepare a new hire's sign-up link; HR approves it before it is sent."""
    try:
        con, client, _ = _guard("draft_registration_invite", params.model_dump(), roles=("hr",))
    except PermissionError as e:
        return _err(e)
    docs = [d for d in onboarding.checklist(params.role_key, params.gender)]
    return _card(con, client, "Intégration", f"Sign-up link for {params.candidate_name}",
                 f"{len(docs)} documents requested. Single-use link, {rules.payroll()['onboarding']['link_valid_days']} days, SMS code.",
                 "Law 25-11 (data notice) · CNAS registration within 10 days",
                 "Link sent to the candidate.")


class OffboardIn(_In):
    employee_id: str
    last_day: _dt.date
    reason: str = Field(..., min_length=3, max_length=200)


@mcp.tool(name="tawzia_draft_offboarding", annotations=DRAFT)
def draft_offboarding(params: OffboardIn) -> str:
    """Prepare an employee's exit (certificate, final pay, access, CNAS, ANEM) as a card."""
    try:
        con, client, _ = _guard("draft_offboarding", params.model_dump(), roles=("hr",))
    except PermissionError as e:
        return _err(e)
    emp = next((e for e in _people() if e.emp_id == params.employee_id), None)
    if emp is None:
        return _err(ValueError("Matricule inconnu."))
    tasks = onboarding.offboarding(emp, params.last_day)
    return _card(con, client, "Intégration", f"Exit of {emp.name} on {params.last_day:%d/%m}",
                 f"{params.reason}. {len(tasks)} tasks: " + ", ".join(t["task"] for t in tasks),
                 "Law 90-11 (work certificate)", "Exit process started.")


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http", port=PORT, stateless_http=True, json_response=True)
    else:
        mcp.run()
