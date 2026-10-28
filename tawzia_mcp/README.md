# tawzia_mcp

Tawzia's public Algerian payroll and labour-law tools, for the AI model or any MCP client.
The tools import the same engine as the app (`core/`), so a rule changed in
`config/dz_payroll_<year>.toml` changes everywhere at once.

All nine tools are read-only. None approves, files, sends, pays, deletes or rejects.

| Tool | What it answers |
|---|---|
| `tawzia_calculate_net_salary` | Net pay, with CNAS, taxable base and every IRG step |
| `tawzia_calculate_employer_cost` | Employer CNAS by branch, total cost |
| `tawzia_check_overtime` | 20 % cap (art. 31), 50 % minimum premium (art. 32), weekly rest |
| `tawzia_check_shift_legality` | Night work rules (art. 27, 28, 29), rest day (art. 33, 36) |
| `tawzia_check_cdd_validity` | Fixed-term contract cases (art. 12) |
| `tawzia_get_compliance_calendar` | G50, CNAS, DAS deadlines for a month |
| `tawzia_get_public_holidays` | Fixed and estimated Hijri holidays |
| `tawzia_search_labour_law` | Summaries of the articles the platform applies |
| `tawzia_explain_payslip_line` | A payslip line in French, Arabic and English |

## Run

```bash
venv/Scripts/python.exe -m tawzia_mcp.server          # stdio
venv/Scripts/python.exe -m tawzia_mcp.server --http   # Streamable HTTP on :8765
```

the AI model Desktop (`model_desktop_config.json`):

```json
{ "mcpServers": { "tawzia": {
  "command": "C:\AI Forge Final\venv\Scripts\python.exe",
  "args": ["-m", "tawzia_mcp.server"],
  "cwd": "C:\AI Forge Final"
} } }
```

Tests: `venv/Scripts/python.exe tests/test_mcp.py`

Not built yet: company-scoped tools behind OAuth (spec B4), rate limiting on the
public HTTP endpoint, the evaluations file (spec B5).
