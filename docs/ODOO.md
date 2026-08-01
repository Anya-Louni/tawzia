# WorkForce.dz and Odoo

Short version: **do not fight Odoo, plug into it.** Odoo is a full ERP that many
Algerian SMEs already run, and it already has community payroll modules for
Algeria. We are not an ERP. We are the **AI intelligence layer** that makes an
Algerian workforce cheaper, legal and better staffed, and we can run standalone
or on top of the customer's Odoo data.

## What we found (research)

- Odoo has working **Algerian payroll modules** on its app store: `dz_paie`,
  `eloapps_hr_dz`, `hr_payroll_algeria`. They handle CNAS, IRG, DAS/301 bis and
  payslips. So "Odoo can't do Algerian payroll" is not true, and is not our pitch.
- Odoo exposes a documented **external API** (XML-RPC on `/xmlrpc/2/common` and
  `/xmlrpc/2/object`, with `execute_kw` search/read/create/write). That is exactly
  what a third-party app uses to read `hr.employee` and `hr.contract`.
- What those modules and Odoo HR do **not** do: demand forecasting, cost-optimal
  legal rostering, the Hijri/Ramadan-aware planning, an adversarial inspection
  simulator, a Journal Officiel watchdog, attrition and model-based retention, or
  a darija assistant.

That gap is our product.

## Positioning: the AI layer, not another ERP

| Capability | Odoo + a DZ payroll module | WorkForce.dz |
|---|---|---|
| Employee records, contracts, payslips | Yes | Reads from Odoo or runs its own |
| CNAS / IRG / DAS payroll math | Yes (community modules) | Yes, and audits Odoo's output |
| Demand forecast on the real Algerian calendar | No | Yes |
| Cost-optimal **legal** roster (overtime cap, rest) | No | Yes (LP optimiser) |
| Hijri / Ramadan / Aid-aware planning | No | Yes (verified engine) |
| Inspection simulator (fines before the inspector) | No | Yes |
| Journal Officiel watchdog + change simulator | No | Yes |
| Attrition + model-based retention negotiator | No | Yes |
| Darija / French AI assistant | No | Yes |

One line for a pitch: **"Odoo keeps your HR records. WorkForce.dz makes them
smart, legal and cheaper - and it reads straight from your Odoo."**

## How the integration works (already built)

`core/odoo_bridge.py` is a real connector:

- `connect_and_fetch(url, db, user, password)` authenticates on Odoo's XML-RPC
  `common` endpoint and `search_read`s `hr.employee` + `hr.contract` from the
  `object` endpoint - the exact calls in Odoo's external-API docs.
- `from_odoo_records(employees, contracts)` maps those records into our
  `hr.Employee` model (role, contract type, hire date), so every AI feature -
  forecasting, the inspection simulator, the Journal Officiel watch, retention -
  runs on the customer's real Odoo data with no re-entry. This mapping is
  unit-tested offline (`python -m core.odoo_bridge`).

Nothing is written back by default (read-only, safe). A later step can push
approved rosters or flags back into Odoo with `create`/`write`.

## Two go-to-market options

1. **Standalone, Odoo-friendly (now).** Sell WorkForce.dz on its own. For Odoo
   shops, "one-click import your employees from Odoo" removes onboarding friction
   and is a strong reason to say yes. This is what `odoo_bridge` enables today.
2. **Odoo Marketplace app (next).** Package a thin Odoo module that embeds our
   API, so we appear inside Odoo's app store where Algerian Odoo users already
   shop. Higher reach, more build (an Odoo addon in Python/XML), best after the
   standalone product has references.

Recommendation: ship option 1 with the pitch above, and use it to win the first
Odoo-running customers, then invest in option 2 once there is demand.

## Sources

- [eloapps_hr_dz - Odoo Apps Store](https://apps.odoo.com/apps/modules/15.0/eloapps_hr_dz)
- [dz_paie (Algerie Payroll) - Odoo Apps Store](https://apps.odoo.com/apps/modules/14.0/dz_paie)
- [hr_payroll_algeria - Odoo Apps Store](https://apps.odoo.com/apps/modules/14.0/hr_payroll_algeria)
- [Odoo External API (XML-RPC) - official docs](https://www.odoo.com/documentation/17.0/developer/reference/external_api.html)
