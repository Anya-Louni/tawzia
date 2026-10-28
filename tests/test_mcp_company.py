"""
Company MCP server: tool list, no forbidden verbs, role checks, drafts become
pending Inbox cards. Runs on a throwaway database.
Run: venv/Scripts/python.exe tests/test_mcp_company.py
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["TAWZIA_DB"] = str(Path(tempfile.mkdtemp()) / "t.db")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tawzia_mcp.company import DemoTokenVerifier, mcp  # noqa: E402

FORBIDDEN = ("approve", "submit", "send", "pay_", "delete", "reject", "file_")


def _call(name, **params):
    res = asyncio.run(mcp.call_tool(name, {"params": {**params, "response_format": "json"}}))
    text = res.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def test_tools_and_safety():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert len(names) == 18, len(names)
    assert not [n for n in names if any(f in n.replace("draft_", "") for f in FORBIDDEN)]
    drafts = [t for t in tools if t.name.startswith("tawzia_draft_")]
    assert drafts and all(not t.annotations.destructive_hint for t in drafts)


def test_list_and_paginate():
    r = _call("tawzia_list_employees", site="OGX", limit=10)
    assert r["total_count"] == 30 and r["has_more"] and r["next_offset"] == 10


def test_payroll_preview_finds_three_issues():
    r = _call("tawzia_preview_payroll", month="2026-10")
    assert r["employees"] == 140 and len(r["anomalies"]) == 3


def test_role_is_enforced():
    os.environ["TAWZIA_MCP_LOCAL_ROLE"] = "auditor"
    try:
        r = _call("tawzia_preview_payroll", month="2026-10")
        assert isinstance(r, str) and "auditor" in r
    finally:
        os.environ["TAWZIA_MCP_LOCAL_ROLE"] = "hr"


def test_draft_creates_pending_card():
    r = _call("tawzia_draft_document", employee_id="DH1000")
    assert r["status"] == "pending"
    cards = _call("tawzia_list_inbox_cards")
    assert any(c["id"] == r["card_id"] for c in cards["items"])


def test_token_verifier_closed_by_default():
    os.environ.pop("TAWZIA_MCP_TOKENS", None)
    assert asyncio.run(DemoTokenVerifier().verify_token("anything")) is None
    os.environ["TAWZIA_MCP_TOKENS"] = json.dumps({"t1": {"client": "cab", "scopes": ["company:DEMO"]}})
    assert asyncio.run(DemoTokenVerifier().verify_token("t1")).client_id == "cab"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
