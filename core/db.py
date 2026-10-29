"""
core/db.py
----------
The staff database: a real database, not a spreadsheet. SQLite for the local
demo; the same schema runs on Postgres in production (brief §8.5).

Security
========
- **Field-level encryption** (AES-256-GCM) of the NIN, ID number, RIB/CCP, CNAS
  number and health fields. The key comes from the TAWZIA_DATA_KEY environment
  variable (32 bytes, base64), never from the repository. In the demo, when it is
  missing, a key is created in `.env`, a git-ignored file.
- **Role-based access** enforced here, in the access layer: an employee sees only
  their own file; a manager sees their team without salary or health; HR sees
  everything; payroll sees pay fields; an auditor reads without writing. In
  production, Postgres adds row-level security (RLS).
- **Log**: every read of a sensitive field and every change is written to
  `action_log` (who, what, when, why), as law 25-11 expects.
- **Minimisation**: health is reduced to "fit: yes, date", never a diagnosis; a
  background check to "done, date, by whom".
"""

from __future__ import annotations

import base64
import datetime as _dt
import json
import os
import secrets
import sqlite3
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("TAWZIA_DB", ROOT / "data" / "tawzia.db"))

ROLES = ("employee", "manager", "hr", "payroll", "auditor")
ENCRYPTED = ("nin", "id_card_no", "rib", "cnas_no", "medical_fit")
PAY_FIELDS = ("gross", "rib")
HEALTH_FIELDS = ("medical_fit",)

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (id TEXT PRIMARY KEY, name TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, company_id TEXT, name TEXT,
    wilaya TEXT, women_night_derogation INTEGER);
CREATE TABLE IF NOT EXISTS employees (id TEXT PRIMARY KEY, company_id TEXT, name TEXT,
    gender TEXT, birth_date TEXT, site_id TEXT, manager_id TEXT,
    nin BLOB, id_card_no BLOB, rib BLOB, cnas_no BLOB, medical_fit BLOB,
    status TEXT DEFAULT 'active');
CREATE TABLE IF NOT EXISTS employment (id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT, contract TEXT, role TEXT, start_date TEXT, end_date TEXT,
    gross REAL, site_id TEXT);
CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT, kind TEXT, status TEXT, file_ref TEXT, retain_until TEXT,
    created TEXT);
CREATE TABLE IF NOT EXISTS onboarding_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT, task TEXT, owner TEXT, due TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS access_grants (id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT, resource TEXT, granted TEXT, revoked TEXT);
CREATE TABLE IF NOT EXISTS leave_ledger (id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT, kind TEXT, days REAL, date TEXT);
CREATE TABLE IF NOT EXISTS payslips (id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT, period TEXT, gross REAL, net REAL, code TEXT);
CREATE TABLE IF NOT EXISTS inbox_cards (id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT, agent TEXT, title TEXT, detail TEXT, law TEXT, decision TEXT,
    payload TEXT, status TEXT DEFAULT 'pending', created TEXT, decided_by TEXT,
    decided_at TEXT);
CREATE TABLE IF NOT EXISTS action_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT, actor TEXT, role TEXT, action TEXT, target TEXT, why TEXT);
CREATE TABLE IF NOT EXISTS consents (id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT, kind TEXT, given TEXT);
"""


# ---------------------------------------------------------------------------
# La clé
# ---------------------------------------------------------------------------

def _key() -> bytes:
    raw = os.environ.get("TAWZIA_DATA_KEY")
    if not raw:
        env = ROOT / ".env"
        lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
        for ln in lines:
            if ln.startswith("TAWZIA_DATA_KEY="):
                raw = ln.split("=", 1)[1].strip()
        if not raw:
            # shortcut: demo-only key creation in the git-ignored .env; production
            # reads it from a secret manager and refuses to start without it.
            raw = base64.b64encode(secrets.token_bytes(32)).decode()
            env.write_text("\n".join(lines + [f"TAWZIA_DATA_KEY={raw}"]) + "\n", encoding="utf-8")
        os.environ["TAWZIA_DATA_KEY"] = raw
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("TAWZIA_DATA_KEY must be 32 bytes, base64-encoded.")
    return key


def encrypt(value: str | None) -> bytes | None:
    if value is None:
        return None
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(_key()).encrypt(nonce, value.encode("utf-8"), None)


def decrypt(blob: bytes | None) -> str | None:
    if blob is None:
        return None
    return AESGCM(_key()).decrypt(blob[:12], blob[12:], None).decode("utf-8")


# ---------------------------------------------------------------------------
# Connexion et journal
# ---------------------------------------------------------------------------

def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def log(con, actor: str, role: str, action: str, target: str, why: str = "") -> None:
    con.execute("INSERT INTO action_log (at, actor, role, action, target, why) VALUES (?,?,?,?,?,?)",
                (_dt.datetime.now().isoformat(timespec="seconds"), actor, role, action, target, why))
    con.commit()


def recent_log(con, limit: int = 50) -> list:
    return [dict(r) for r in con.execute(
        "SELECT * FROM action_log ORDER BY id DESC LIMIT ?", (limit,))]


# ---------------------------------------------------------------------------
# Chargement de la société de démonstration
# ---------------------------------------------------------------------------

def _fake_digits(rng, n: int) -> str:
    return "".join(str(int(d)) for d in rng.integers(0, 10, n))


def seed(con=None) -> sqlite3.Connection:
    """Load the fictional company when the database is empty. Idempotent."""
    import numpy as np

    from . import seed_company as sc
    con = con or connect()
    if con.execute("SELECT COUNT(*) FROM employees").fetchone()[0]:
        return con
    rng = np.random.default_rng(7)
    con.execute("INSERT INTO companies VALUES (?,?,?)",
                ("DEMO", sc.COMPANY["name"], sc.COMPANY["legal_note"]))
    for sid, s in sc.SITES.items():
        con.execute("INSERT INTO sites VALUES (?,?,?,?,?)",
                    (sid, "DEMO", s["name"], s["wilaya"], int(s["women_night_derogation"])))
    people = sc.people()
    sup = {sid: [e.emp_id for e in people if e.site == sid and e.role_key == "supervisor"]
           for sid in sc.SITES}
    for e in people:
        mgr = sup[e.site][0] if e.role_key != "supervisor" and sup[e.site] else None
        # Identifiants inventés, au bon format, pour une société fictive.
        con.execute(
            "INSERT INTO employees (id, company_id, name, gender, birth_date, site_id, "
            "manager_id, nin, id_card_no, rib, cnas_no, medical_fit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (e.emp_id, "DEMO", e.name, e.gender, e.birth_date.isoformat(), e.site, mgr,
             encrypt(_fake_digits(rng, 18)), encrypt(_fake_digits(rng, 9)),
             encrypt("007" + _fake_digits(rng, 17)), encrypt(_fake_digits(rng, 12)),
             encrypt(f"apte, {e.hire_date.isoformat()}")))
        con.execute("INSERT INTO employment (employee_id, contract, role, start_date, gross, site_id) "
                    "VALUES (?,?,?,?,?,?)",
                    (e.emp_id, e.contract, e.role_key, e.hire_date.isoformat(),
                     round(e.monthly_gross()), e.site))
    con.commit()
    log(con, "system", "hr", "seed", "DEMO", "loading the fictional company")
    return con


# ---------------------------------------------------------------------------
# Lecture selon le rôle
# ---------------------------------------------------------------------------

def _visible(role: str, field: str, own: bool, team: bool) -> bool:
    if role == "hr":
        return True
    if role == "employee":
        return own
    if role == "manager":
        return team and field not in PAY_FIELDS + HEALTH_FIELDS + ("nin", "id_card_no", "cnas_no")
    if role == "payroll":
        return field in PAY_FIELDS + ("cnas_no", "nin")
    if role == "auditor":
        return field not in HEALTH_FIELDS
    return False


def get_employee(con, emp_id: str, *, actor: str, role: str, why: str = "") -> dict | None:
    """An employee's file, reduced to what the role may see.

    Hidden sensitive fields read "masked". Every encrypted field actually read is
    logged."""
    if role not in ROLES:
        raise PermissionError(f"Unknown role: {role}")
    row = con.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()
    if row is None:
        return None
    own = actor == emp_id
    team = row["manager_id"] == actor
    if role == "employee" and not own:
        log(con, actor, role, "read_refused", emp_id, why)
        raise PermissionError("An employee only sees their own file.")
    if role == "manager" and not team:
        raise PermissionError("This employee is not in your team.")
    job = con.execute("SELECT * FROM employment WHERE employee_id = ? ORDER BY id DESC LIMIT 1",
                      (emp_id,)).fetchone()
    out = {"id": row["id"], "name": row["name"], "site": row["site_id"],
           "gender": row["gender"], "birth_date": row["birth_date"],
           "contract": job["contract"], "role": job["role"], "start_date": job["start_date"]}
    out["gross"] = job["gross"] if _visible(role, "gross", own, team) else "masked"
    read = []
    for f in ENCRYPTED:
        if _visible(role, f, own, team):
            out[f] = decrypt(row[f])
            read.append(f)
        else:
            out[f] = "masked"
    if read:
        log(con, actor, role, "read:" + ",".join(read), emp_id, why or "file consultation")
    return out


def export_own_data(con, emp_id: str) -> str:
    """"My data": everything stored about me, as JSON (right of access)."""
    data = get_employee(con, emp_id, actor=emp_id, role="employee", why="right of access")
    data["documents"] = [dict(r) for r in con.execute(
        "SELECT kind, status, created FROM documents WHERE employee_id = ?", (emp_id,))]
    log(con, emp_id, "employee", "export", emp_id, "right of access, law 25-11")
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Cartes de la boîte de décisions venues de l'extérieur (MCP, onboarding)
# ---------------------------------------------------------------------------

def add_card(con, *, source: str, agent: str, title: str, detail: str, law: str,
             decision: str, payload: dict | None = None) -> int:
    cur = con.execute(
        "INSERT INTO inbox_cards (source, agent, title, detail, law, decision, payload, created) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (source, agent, title, detail, law, decision, json.dumps(payload or {}, ensure_ascii=False),
         _dt.datetime.now().isoformat(timespec="seconds")))
    con.commit()
    log(con, source, "agent", "card_created", str(cur.lastrowid), title)
    return cur.lastrowid


def pending_cards(con) -> list:
    return [dict(r) for r in con.execute(
        "SELECT * FROM inbox_cards WHERE status = 'pending' ORDER BY id")]


def decide_card(con, card_id: int, verdict: str, actor: str) -> None:
    if verdict not in ("approved", "rejected"):
        raise ValueError("verdict must be approved or rejected")
    con.execute("UPDATE inbox_cards SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
                (verdict, actor, _dt.datetime.now().isoformat(timespec="seconds"), card_id))
    con.commit()
    log(con, actor, "hr", verdict, f"card {card_id}", "human decision")


if __name__ == "__main__":
    import tempfile
    os.environ["TAWZIA_DATA_KEY"] = base64.b64encode(b"k" * 32).decode()
    DB_PATH = Path(tempfile.mkdtemp()) / "t.db"
    con = seed(connect())
    assert con.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 140
    raw = con.execute("SELECT nin FROM employees LIMIT 1").fetchone()[0]
    assert raw != decrypt(raw).encode() and not raw.isdigit(), "the NIN must be encrypted"
    eid = con.execute("SELECT id FROM employees WHERE manager_id IS NOT NULL LIMIT 1").fetchone()[0]
    mgr = con.execute("SELECT manager_id FROM employees WHERE id = ?", (eid,)).fetchone()[0]
    hr_view = get_employee(con, eid, actor="rh1", role="hr")
    assert len(hr_view["nin"]) == 18
    m = get_employee(con, eid, actor=mgr, role="manager")
    assert m["gross"] == "masked" and m["nin"] == "masked" and m["medical_fit"] == "masked"
    try:
        get_employee(con, eid, actor="DH9999", role="employee")
        raise AssertionError("an employee read someone else's file")
    except PermissionError:
        pass
    assert get_employee(con, eid, actor=eid, role="employee")["rib"].startswith("007")
    cid = add_card(con, source="mcp", agent="Guichet", title="t", detail="d", law="l", decision="x")
    decide_card(con, cid, "approved", "rh1")
    assert not pending_cards(con)
    assert any(r["action"].startswith("read") for r in recent_log(con))
    print("  encrypted staff database: ok")
