# Tawzia demo guide

Tawzia is an AI HR department for Algerian companies: agents do the HR work,
HR only approves. This guide lists every screen and gives a demo script that
fits in ten minutes.

The demo runs on **Demo Handling & Logistique**, a fictional company with 140
employees on two sites (Algiers airport hub and warehouse, Ouargla southern
base). The data is simulated and labelled as such on every screen. The labour
law, payroll rules, calendar and weather are real.

## Screens

### Decisions
- **Approval inbox** (home): every agent's prepared work as a card, with the
  law that applies, the money at stake and the minutes saved. Approve, edit or
  reject. Batch-approve routine items. Nothing leaves without a click.
- **Employee desk**: employees ask in English, French, Darija or Arabic for an
  attestation, a payslip explanation or leave. Documents come out ready to sign.

### People
- **Employees**: the encrypted staff register, with role-based masking.
- **Requests and attendance**: leave and absence requests weighed against
  forecast load; who is late or absent today.
- **Skills and mobility**: the team skills gap, a costed training plan, and
  train-or-hire for an open role.
- **Retention**: leaving risk per employee and the cheapest lever to keep them,
  with the conversation written for the manager.

### Scheduling
- **Weekly schedule**: a legal roster solved by CP-SAT under Law 90-11 (night
  work, under-19s, overtime cap, weekly rest), with a Ramadan mode.
- **Demand forecast**, **Schedule and cost**, **Sector analysis**: the forecast
  behind the roster, its loaded cost, and the sector-specific view.

### Hiring
- **Write a job post**: one sentence in, a publishable post out, checked
  against what you pay, the law, and who in house could hold the role.
- **Sourcing channels**: real Algerian channels (universities, CFPA/INSFP,
  ANEM, job sites) ranked by fit, distance, cost and lead time.
- **Candidates**: the ranked pool with reasons and a four-fifths bias audit.
- **Onboarding**: sign-up links, document checks, probation ends.

### Payroll and filings
- **Payroll**: the month's payslips (CNAS, IRG), bilingual French/Arabic
  payslips, the bank transfer file, and the labour-law guard.
- **Deadlines and filings**: G50, CNAS and DAS drafts with due dates and portals.
- **Anomaly detection**: rules plus an unsupervised model over payroll and
  attendance.
- **Inspection simulator**: run the labour inspection on yourself first.
- **Official Journal watch**: tracked rules, your status, and the cost of a change.

### Settings
Ask Tawzia (assistant), PDF to AI text, Company data import, Privacy (Law 25-11
controls and action log), Scenario simulator, Dashboard, Proof, Algerian
calendar, Business case, Sources.

## Ten-minute script

1. **Open the Approval inbox.** "This is the HR department. The agents worked
   overnight; this is what is waiting for a signature." Point at the count,
   the hours saved and the DZD at stake.
2. **Open a payroll card.** Show the salary below the SNMG the agent caught,
   with the article. Approve the routine cards in one batch.
3. **Filings.** Open Deadlines and filings: the G50 and CNAS drafts are ready,
   with the date and the official portal. "Tawzia never files for you. You file
   in two minutes instead of two days."
4. **Weekly schedule.** Solve the week for Ouargla. Show that the under-19s
   are never on nights and the overtime cap holds. Switch on Ramadan mode.
5. **Employee desk.** Ask in Darija for a work attestation. It comes out in
   French and Arabic, ready to sign.
6. **Hiring.** Write a job post from one sentence, then show the ranked
   candidates and the bias audit.
7. **Privacy.** Show masking before AI calls, the local-model switch and the
   action log. "Law 25-11 by design."
8. **Close.** "Agents do the HR work. HR approves. Built for Algerian law."

## Before a demo

```bash
venv/Scripts/python.exe tools/check_pages.py
```

The first run warms every cache so screens open instantly.
