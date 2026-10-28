"""
MCP server checks: tool list, safety rule, and the payroll vectors through the
tool layer. Run: venv/Scripts/python.exe tests/test_mcp.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tawzia_mcp.server import mcp  # noqa: E402

FORBIDDEN = ("approve", "submit", "send", "pay_", "delete", "reject", "file_")


def _call(name, **params):
    res = asyncio.run(mcp.call_tool(name, {"params": {**params, "response_format": "json"}}))
    text = res.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def test_tools_listed_and_safe():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert len(names) == 9, names
    assert not [n for n in names if any(f in n for f in FORBIDDEN)]
    assert all(t.annotations.read_only_hint and not t.annotations.destructive_hint for t in tools)


def test_net_salary_vector():
    r = _call("tawzia_calculate_net_salary", gross=60000)
    assert (r["irg"], r["net"]) == (7042, 47558)


def test_net_salary_bad_input_is_actionable():
    r = _call("tawzia_calculate_net_salary", items={"mystere": 10})
    assert isinstance(r, str) and "Unknown pay item" in r


def test_shift_women_night():
    r = _call("tawzia_check_shift_legality", start="22:00", end="06:00", worker_age=30,
              worker_gender="F", site_women_night_derogation=False)
    assert not r["legal"] and r["violations"][0]["article"].endswith("29")


def test_overtime_cap():
    r = _call("tawzia_check_overtime", hours_per_day=[10, 10, 10, 10, 10, 0, 0], hourly_wage=200)
    assert not r["legal"] and r["overtime_hours"] == 10


def test_calendar_and_holidays():
    r = _call("tawzia_get_compliance_calendar", month="2026-11", headcount=80)
    assert any("G50" in d["label"] for d in r["deadlines"])
    h = _call("tawzia_get_public_holidays", year=2027)
    assert any("Fitr" in x["name"] for x in h["holidays"])


def test_law_search():
    r = _call("tawzia_search_labour_law", query="heures supplémentaires")
    assert r["articles"][0]["article"] == "art. 31"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
