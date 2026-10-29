# Tawzia rebuild brief (for the build team)

Research date: 28 October 2026. Every legal number below has a source at the bottom. Numbers marked **[verify]** come from a single private source or conflict between sources; make them config values, never hardcode.

---

## 0. Build instructions

1. Read this whole file before touching code. Then read the existing Tawzia repo and list every current page/feature.
2. Map each existing feature to section 4 (keep / merge / cut). Do the cuts first.
3. Build in the order of section 9. Ship a working demo after each stage.
4. Keep the existing Python ML where it says "reuse". Do not rewrite working math for style.
5. Never present simulated data as real. Every screen that uses simulated data shows a small "Demo data" chip.
6. Writing style for all UI copy: short, warm, direct. No em dashes. French first, English and Arabic toggles.
7. Also read `TAWZIA_BUSINESS_AND_MCP.md`. Part B there is the MCP server spec: the same tool layer the in-app agents use. Its build steps slot in after stage 3 below.

---

## 1. The problem with the current version

Too many pages, overlapping features, dashboards that make HR *look at* things instead of *getting things done*. Choice overload is a real design cost: every extra menu item makes the first click slower (Hick's law), and an HR manager who opens 12 tabs still does the work herself.

## 2. The new concept (one sentence)

**Tawzia is an AI HR department for Algerian companies: agents do the HR work, HR only approves.**

The whole product reorganizes around one idea: **the Approval Inbox**. Every agent finishes a task and drops a card in the inbox: *what I did, why, what law I followed, approve / edit / reject*. HR's job becomes reading cards and tapping Approve. That is the "they just sit at their desks" promise, made concrete and safe.

Pitch line for the jury: *"Other HR software in Algeria digitizes forms. Tawzia fills them, checks them against the law, files them, and asks you to sign."*

## 3. Why this wins (evidence for the pitch)

- **HR is drowning in admin.** Eagle Hill Consulting survey (Sept 2026): 51% of HR professionals spend at least half their week on routine admin; 78% re-enter the same data in several systems; 91% need 2+ systems for one HR task; 36% often can't tell how an AI output was produced. → Tawzia: one system, agents do the entry, every AI output shows its reasoning.
- **Algerian HR is uniquely paperwork-heavy.** Monthly G50 IRG filing by the 20th, CNAS payments, the annual DAS, CNAS affiliation within 10 days of each hire, the ANEM 5-working-day vacancy rule with per-candidate outcome reporting, and since 2025 the data-protection law 25-11. Foreign tools (Workday, SAP) don't know any of this.
- **Local competitors digitize but don't automate.** Talenteo (Algiers, launched 2022, funded by 216 Capital in 2025) and Almawarid (Oran) offer payroll/leave/attendance SaaS for SMEs. Coverage of them mentions no AI agents. Tawzia's lane: the agentic layer on top of Algerian compliance.
- **Global direction confirms the bet.** Workday, SAP Joule, Oracle, UKG and Darwinbox all shipped HR *agents* in 2025-2026 (payroll validation agents, scheduling agents, request-handling agents). Nobody does it for Algerian law in French/Arabic/Darija.
- **Scheduling stability pays.** Gap randomized trial (28 stores): more stable, predictable schedules raised median sales 7% and labor productivity 5%, partly via better retention. Use this to justify the scheduler's "stability" objective.
- **Social impact.** ONS (Oct 2024): unemployment 12.7%, youth (16-24) 29.3%, women's labour force participation 19.2%. Tawzia's hiring agent cuts ANEM friction and its bias audit protects women candidates. Frame it as "faster, fairer hiring", with numbers from your demo, never invented outcome claims.

## 4. Feature triage (keep / merge / cut)

| Current module | Decision | New home |
|---|---|---|
| Demand forecasting (HistGradientBoosting, Hijri + weather) | **Keep, reuse code** | Input to Scheduler agent, shown as one line ("Expected load +18% Thursday, Ramadan + heat") never as its own page |
| Roster optimizer (`scipy.linprog`) | **Upgrade** | Replace with OR-Tools CP-SAT (handles legal hard constraints + fairness). Keep linprog only as fallback |
| Payroll (SNMG/CNAS/IRG) | **Keep, rewrite engine to spec in §7** | Payroll agent |
| Compliance alerts + portal links | **Merge** | Compliance agent → feeds Inbox + a single Calendar view |
| CV screening (TF-IDF) | **Upgrade** | Recruiter agent: LLM structured extraction + embedding similarity + explainable score + bias audit |
| Attrition/retention (manual weights) | **Merge, relabel honestly** | Retention agent; call it "rule-based early warning" until trained on client data |
| Anomaly detector (IsolationForest) | **Keep, reuse** | Hidden inside Payroll agent ("3 anomalies found") |
| Digit recognition (SVC) | **Cut from UI** | If useful, becomes invisible OCR in Documents agent; otherwise delete |
| Aviation delay-cascade module | **Merge** | "Airport & logistics pack": an extra demand signal for the Scheduler. No separate page |
| Chatbot | **Upgrade** | "Ask Tawzia" command bar (HR side) + Employee Assistant (worker side) that can *act* via tools |
| Marketing site + pricing | **Separate** | Move to its own route `/` landing; app lives at `/app`. Keep pricing to 3 tiers max |
| Any other page not in §5 | **Cut or merge** | List it, propose where it goes, ask Anya before deleting |

## 5. Information architecture: 5 screens, nothing else

Left nav has five items plus settings, no more:

1. **Inbox** (default screen). Agent cards sorted by deadline. Top strip: "Hours saved this month: 46h" (sum of per-task time estimates, label as estimate) and "Next legal deadline: G50, 20 Nov, 4 days".
2. **People.** One employee = one page with a timeline (hired, contract, leaves, payslips, documents, schedule). Search, nothing else on the list view.
3. **Planning.** The AI schedule (week grid). One button: "Generate". Violations shown inline with the law article.
4. **Hiring.** One pipeline per open role: Posting → ANEM window → Candidates → Interviews → Offer → Onboarding.
5. **Payroll & Filings.** Monthly run + legal calendar (G50, CNAS, DAS) + generated files.

Global: **"Ask Tawzia" command bar** (Ctrl+K and a mic button). Natural language that executes through the same agent tools, e.g. "Ramadan starts on the 18th, redo next week's schedule" or "attestation de travail for Amina Belkacem".

UX rules (enforce them):
- One primary action per screen.
- Every AI card has these parts and only these: **What I did · Why · Law/source · [Approve] [Edit] [Reject]**.
- No chart unless it changes a decision. No KPI walls.
- Progressive disclosure: details behind "See why".
- Empty states tell you what the agent is waiting for.

## 6. The agents (each one replaces a job HR does today)

Build each agent as a Python service with explicit tools, run by an LLM tool-use loop. Deterministic math (payroll, constraints) stays in code; the LLM plans, explains, drafts text, and extracts data. **No agent ever sends, files, pays, hires or rejects without a human Approve click.**

### 6.1 Employee Assistant (the demo's star)
- Channel: a WhatsApp-style chat (in the demo, a phone mockup inside the app; real WhatsApp/Telegram integration listed as roadmap).
- Understands French, Arabic, and Algerian Darija (Latin and Arabic script). Test Darija carefully with real phrasing; don't promise perfect Darija.
- Tools: leave balance, request leave, request shift swap, get last payslip, request *attestation de travail* / *attestation de salaire*, report absence.
- Answers about rules must cite the stored policy/law text (retrieval over a small curated corpus: law 90-11 articles in §8, the company règlement intérieur). If the answer isn't in the corpus: "I'll ask HR" → creates an Inbox card. This prevents the known failure of HR bots inventing leave entitlements.
- Demo moment: worker types *"nheb attestation de travail lel bank"* → agent generates a bilingual FR/AR PDF → card in HR Inbox → Approve → delivered to the worker. 20 seconds end to end.

### 6.2 Scheduler agent (kept as the special feature, made Algeria-proof)
- Inputs: demand forecast (existing model), skills, contracts, availability, employee preferences, approved leaves.
- Solver: OR-Tools CP-SAT. Hard constraints from §8.2. Soft objectives: cover demand, minimize overtime cost, **schedule stability week to week**, fairness of nights/Fridays/holidays, respect preferences.
- Output card: "Next week's schedule is ready. 0 legal violations. Overtime cost 38,400 DA (−22% vs last week). 2 swap requests auto-resolved." + diff vs last week.
- Shift swaps: worker requests in chat → agent finds a legal swap partner → both confirm → card to manager.
- Re-plan on events: sickness message at 6:00 → agent proposes a replacement within legal rest/overtime limits.
- Ramadan mode and Hijri holidays come from the existing calendar code.
- Answer to "does AI scheduling work in Algeria?": yes, in shift-based sectors (airports/ground handling, hospitals and clinics, call centres, factories, retail, security). Office SMEs barely need it, so the scheduler is a **module you turn on**, and the core product (payroll, filings, hiring, documents) sells to everyone.

### 6.3 Payroll agent
- Runs on the 25th (configurable): pulls attendance, overtime, leaves, primes → computes with the engine in §7 → runs the existing IsolationForest + rule checks → one card: "October payroll ready: 142 employees, total net 8.41M DA, 3 issues."
- Issue examples: overtime above the 20% cap (art. 31), base below SNMG, IRG bracket jump explained, an employee paid during unrecorded absence.
- Generates payslips (PDF, FR/AR), the bank transfer file (CSV), and the journal entries.

### 6.4 Compliance & Filings agent
- Owns the legal calendar (§8.3). Prepares each filing *draft* with all figures (G50 IRG line, CNAS contribution summary, DAS annual file) and links to the official portals (Jibaya'tic for G50, CNAS e-services). It never submits; HR submits on the portal.
- Watches events: new hire → CNAS affiliation countdown (10 days); work accident → declaration deadline; contract end dates; CDD renewal legality.
- Cites the article for every alert.

### 6.5 Recruiter agent (+ ANEM handling)
- Writes the job post from a 3-line manager brief (FR/AR).
- **ANEM module (strong local differentiator):** files the vacancy, runs the **5-working-day countdown** (law 20-03), ingests ANEM's nominative candidate list, schedules contact with each referred candidate, and generates the per-candidate outcome report the law requires. After 5 working days with no fill → unlocks direct hiring and reminds HR to inform ANEM of the hire.
- CV ranking: LLM extracts structured fields (skills, years, education, languages, wilaya) → embedding similarity + must-have rules → score with a plain-language explanation per candidate. HR sees ranked list + filters.
- **Bias audit panel:** selection rate by gender (and age band if provided) with the four-fifths ratio; warning when a group's rate falls below 80% of the top group. Names, photos and gender hidden from the LLM scoring prompt.
- Proposes interview slots, drafts invites, drafts the offer and the contract. Checks CDD legality against art. 12 cases.

### 6.6 Registration & Onboarding agent (from "offer accepted" to "fully productive")

The goal: HR types nothing. The new hire fills their own file from their phone, the agent checks it, and HR approves one card.

**Step 1: Self-registration link (pre-boarding).** When an offer is approved, the agent sends the new hire a secure one-time link (expires in 7 days, phone OTP). Mobile-first form in FR/AR/EN, saved as they go. They photograph or upload:
- National ID card (front/back) or passport → OCR extracts name, date and place of birth, NIN, card number, expiry.
- Extrait de naissance; fiche familiale if married (both used for CNAS affiliation).
- CNAS number if they already have one.
- RIB / CCP for salary.
- Diplomas and work certificates from previous employers.
- Service national status (men), medical aptitude certificate, ID photo.
- Emergency contact, address, family situation.
- Signed acknowledgements: règlement intérieur, confidentiality agreement, data-protection notice (law 25-11), IT charter.
- The exact checklist is **configurable per company and per role**. Ship a default list marked [verify]; requirements vary by employer and sector. Public bodies, for example, may no longer require the nationality certificate when an ID copy is provided, and some can't require bulletin n°3 of the criminal record. Never hardcode a document as legally required.

**Step 2: Agent verification.** OCR + LLM extraction fills the record, then checks: ID not expired, names match across documents, NIN format valid, RIB key valid, age ≥ legal minimum and flags under-19 (no night shifts, art. 28), missing or blurry documents. Problems go back to the new hire automatically ("Your ID photo is blurry, please retake it"), so HR never chases paperwork.

**Step 3: One approval card for HR.** "Amina Belkacem's file is complete and verified. 11/11 documents. 1 note: ID expires in 4 months. [Approve hire] [See file]". On approve, the agent creates the employee record and launches everything below in parallel:
- **Contract** generated (CDI/CDD with art. 12 check), sent for e-signature. Law 26-02 of 17 Feb 2026 now governs electronic signatures and trust services in Algeria; until certified providers are operational, keep a "print and sign" fallback and store the signed scan.
- **CNAS affiliation draft** (immatriculation or affiliation, sécu 01 data) with the 10-day countdown and a link to teledeclaration.cnas.dz. HR submits.
- **ANEM hire notice** draft.
- **Payroll setup:** salary, primes, IRG status, bank details (pending approval of the first payroll).
- **Schedule:** first two weeks placed by the Scheduler, with a buddy on the same shifts.
- **Access & equipment checklist:** badge, uniform/PPE, laptop, email and app accounts, locker. Each item assigned to an owner (IT, security, logistics) with a due date before day 1.
- **Welcome message** in the Employee Assistant: date, address, who to ask for, what to bring, first-day agenda.

**Step 4: Onboarding journey (the part the best-run HR teams do well).** A per-role plan the agent runs and tracks:
- **Before day 1:** documents, accounts, badge, equipment ready. Manager gets a prep card 3 days before.
- **Day 1:** welcome, safety and security briefing (evacuation, access rules, confidentiality), IT setup, meet the buddy.
- **Week 1:** mandatory trainings with quiz and signed completion (e.g. safety, data protection, code of conduct, anti-harassment; sexual harassment is a disciplinary matter in Algerian law, so this one is worth making standard).
- **Day 30 / 60 / 90 check-ins:** short questions to the employee in the assistant ("Do you have what you need?"), answers summarised for the manager. Early-warning to the Retention agent if answers turn negative.
- **End of trial period:** the agent reminds the manager before the trial ends (max 10 months, 12 for highly qualified posts, art. 18), drafts the evaluation form, and creates a "Confirm / Extend / End" card. Either party can end during the trial without notice or indemnity (art. 20), so the reminder protects both sides from forgotten deadlines.
- **Offboarding (mirror flow):** certificat de travail, final pay (leave balance paid out), equipment and badge return, account closure, CNAS/ANEM updates, exit survey.

**Sensitive-role onboarding (set per role, no special mode):**
Some roles need more vetting: airside airport staff, cash handlers, security guards, anyone with access to confidential data. HR marks a role as sensitive once, and every hire into it automatically gets the extra steps. No toggle, no separate product, it's part of how roles work.
- Reference checks: the agent drafts emails to referees, HR sends, answers are summarised on the file.
- Background-check result recorded as "completed / date / by whom". Store the result, never the raw criminal-record document.
- Access level per person (which buildings, which systems), reviewed automatically on role change and revoked the moment someone leaves.
- Interface and documents follow the company's language setting (FR/AR/EN), so an English-speaking admin team uses the same product as everyone else.

**Document factory** (unchanged): attestations, certificats de travail, mutation letters, leave decisions, bilingual templates, QR verification code on every issued document.

### 6.7 Retention agent
- Weekly: flags people with risk signals (rising absences, many night/Friday shifts, schedule instability, long time since a raise, overtime above cap). Suggests a *concrete action the system can do* ("give Yacine two stable weeks, the scheduler can do it, Approve?").
- Label honestly as rule-based until real data exists.

## 7. Payroll engine spec (implement as written, with unit tests)

All rates in a dated config file (`config/dz_payroll_2026.yaml`) with `valid_from` so future finance laws only need a new file. PLF 2027 (adopted in Council of Ministers 4 Oct 2026) announces salary increases but no published IRG change yet; re-check in January 2027.

- **SNMG:** 24,000 DA/month from 1 Jan 2026 (presidential decree 26-01). Previous: 20,000.
- **CNAS employee:** 9% of the contributable base.
- **CNAS employer:** 25% + 0.5% social works = 25.5%; total 34.5% per the branch table (social insurance 11.5/1.5, work accidents 1.25/0, pension 11/6.75 + 0.5 social works, unemployment 1/0.5, early retirement 0.25/0.25). **[verify]** Several sources state employer 26% / total 35%. Keep it in config and show the breakdown on the payslip.
- **Contributable vs taxable allowances:** some primes are not subject to CNAS. Make each pay item carry two flags `cnas_subject`, `irg_subject`. Do not guess which primes are which; ship with a small default list marked [verify].
- **IRG (monthly brackets = annual article 104 brackets / 12):**
  - 0 to 20,000: 0%
  - 20,001 to 40,000: 23%
  - 40,001 to 80,000: 27%
  - 80,001 to 160,000: 30%
  - 160,001 to 320,000: 33%
  - above 320,000: 35%
- `taxable = gross_irg_subject − cnas_employee`
- If `taxable ≤ 30,000` → IRG = 0.
- `irg = barème(taxable)`; `abatt = clamp(0.4 × irg, 1000, 1500)`; `irg −= abatt`.
- If `30,000 < taxable ≤ 35,000` → `irg = irg × 137/51 − 27,925/8`.
- Disabled workers and general-regime retirees with `30,000 < taxable ≤ 42,500` → `irg = irg × 93/61 − 81,213/41` (does not combine with the line above).
- Floor at 0, round to the dinar.
- **Test vectors (all verified against published examples):**
  - gross 24,000 → CNAS 2,160, taxable 21,840, IRG 0
  - gross 60,000 → CNAS 5,400, taxable 54,600, IRG 7,042, net 47,558
  - taxable 35,000 → IRG 2,070
  - retiree/disabled taxable 32,000 → IRG ≈ 543.9
  - taxable 30,000 → IRG 0
- **Overtime:** premium ≥ 50% of the normal hourly wage (art. 32). Companies can configure higher rates per collective agreement. Some guides list 25/50/75/100% tiers; the legal floor in the 90-11 text is 50%, so never go below it.

## 8. Algerian rules the agents enforce

### 8.1 Legal texts in force
- Law 90-11 (labour relations, amended; last amendment cited: law 17-11 of 2017). A new labour code has been drafted for years but no adoption was found. Treat 90-11 as current.
- Ordinance 97-03: 40-hour legal week.
- Law 04-19 on placement, amended by law 20-03 (2020): ANEM 5-working-day rule.
- Law 18-07 on personal data, amended by law 25-11 (24 July 2025).

### 8.2 Scheduler hard constraints
- 40 h/week legal duration (ord. 97-03), spread over at least 5 days **[verify]**; max 12 h/day including breaks **[verify]**.
- Overtime ≤ 20% of legal duration (art. 31) → 8 h/week.
- Night work = 21:00 to 05:00 (art. 27).
- No night work for anyone under 19 (art. 28).
- Night work for women prohibited unless a labour-inspector derogation exists (art. 29) → per-site boolean `night_derogation_women`; without it the solver cannot place women on 21:00-05:00 shifts. Show this as a legal guard with the article cited. Sensitive point: present it neutrally as compliance, and note that the derogation unlocks equal access to night roles.
- One full rest day per week, normally Friday (art. 33). Working a legal rest day → equal compensatory rest (art. 36). Weekly rest may move for production reasons (art. 37).
- Public holidays: 1 Jan, 1 May, 19 Jun, 5 Jul, 1 Nov + Mouloud, Eid al-Fitr (2 days), Eid al-Adha (2 days), 1 Muharram, Ashura. Hijri dates from the existing calendar code. Confirm the list (e.g. Yennayer, 12 Jan, has been a national holiday since 2018) **[verify]**.
- Ramadan: public administrations worked 08:30-15:00, Sunday to Thursday in Ramadan 2026. Private companies: configurable Ramadan hours.
- Leave: 2.5 days per month worked, max 30 calendar days per year (art. 41); reference year 1 July to 30 June (art. 40); southern wilayas get at least 10 extra days (art. 42).
- Special paid absences: 3 working days for listed family events (art. 54).

### 8.3 Compliance calendar (Compliance agent)
| Obligation | Deadline | Source |
|---|---|---|
| G50 (IRG withheld on salaries, plus TVA etc.) | 1st to 20th of the following month; online on Jibaya'tic mandatory for réel regimes since 1 Jan 2026; late: 10% + 3%/month, capped 25% | upgrowth G50 guide **[verify on mfdgi.gov.dz]** |
| CNAS contributions | Within 15 days after the due date; monthly if >9 workers, quarterly if <10 | upgrowth CNAS guide **[verify]** |
| DAS (annual salary declaration, CNAS) | Before 31 January | algerie-eco, Jan 2026 |
| New hire CNAS affiliation | Within 10 days of hiring | upgrowth, lamacta |
| ANEM vacancy | File before recruiting; 5 working days for ANEM to fill; then direct hire allowed, inform ANEM | law 20-03 via Emploitic |
| Règlement intérieur | Mandatory from 20 workers (art. 75) | law 90-11 |
| Work accident declaration | 48 hours **[verify]** | lamacta |
| Trial period | Max 10 months, 12 for highly qualified posts (art. 18) | law 90-11 |
| CDD | Only in the cases of art. 12 (replacement, temporary surge/seasonal, inherently temporary work) | law 90-11 |

### 8.4 Data protection (law 25-11) and AI governance: build it in, show it to the jury
- **PII redaction before any LLM call** (names, phone, NIN, addresses replaced by tokens, restored after). Cross-border transfers need adequate safeguards under 25-11 and local hosting is recommended, so offer a "local model" setting (e.g. an open-weights model via Ollama) as the sovereign deployment option.
- Processing register + **action log** for every agent step (who/what/when/why): 25-11 expects logging of collection, consultation, modification, erasure.
- Breach notification: ANPDP within 5 days **[verify against JO text]**. Add a simple incident register page in Settings.
- Biometric attendance (if integrated later): ANPDP deliberation of 6 May 2026 says employers need no employee consent for attendance use. They do need a **prior declaration to the ANPDP**.
- Human-in-the-loop on every hire/reject/pay/filing decision. EU AI Act classes recruitment AI as high-risk; its obligations now apply from 2 Dec 2027 after the Digital Omnibus. Use it and NYC Local Law 144 (bias audits) as the design benchmark, and say so in the pitch: "built to the strictest standard we could find, ahead of Algerian rules."

### 8.5 The employee database: digital and secure by design

Real database, not spreadsheets or JSON files. Postgres (SQLite only for the local demo).

**Data model (core tables):** `companies`, `sites`, `employees` (identity), `employment` (contract history: type, dates, role, salary, site), `documents` (metadata + encrypted file reference), `onboarding_tasks`, `access_grants`, `leave_ledger`, `payslips`, `inbox_cards`, `action_log`, `consents`.

**Security rules the build must implement:**
- **Field-level encryption** for NIN, ID card number, RIB/CCP, CNAS number, health-related fields (AES-256-GCM, keys in environment/secret manager, never in the repo). Files encrypted at rest in object storage.
- **Role-based access:** employee sees only their own file; manager sees their team without salary or health fields; HR sees all; payroll role sees pay fields; auditor is read-only. Enforce in the API layer and with Postgres row-level security.
- **Data minimisation:** collect only what the configured checklist needs. Medical certificates store "fit for work: yes, date" plus the file, never diagnoses. Background checks store the result, never the record itself.
- **Retention schedule** per document type, with automatic deletion or archiving after the period (configurable, defaults marked [verify]).
- **Audit trail:** every view of a sensitive field and every change is logged in `action_log` (who, what, when, why). 25-11 expects logging of collection, consultation, modification and erasure.
- **Employee rights:** a "My data" page where the employee sees what's stored, downloads it, and requests corrections (creates an Inbox card).
- **Secure links:** one-time, expiring, OTP-protected registration links; rate limiting; no personal data in URLs.
- **Hosting:** Algerian or local hosting option; PII redaction before any external LLM call (already in §8.4).
- **Backups:** encrypted, tested restore, documented in Settings.
- **Demo honesty:** the demo runs on fictional seed data. Say on stage that production deployment needs a security review and ANPDP declarations.

## 9. Build order

1. **Skeleton + cuts.** Landing at `/`, app at `/app`, 5-item nav, Inbox with seeded cards. Seed company: a *fictional* Algiers ground-handling and logistics firm, ~140 employees, realistic Algerian names, mixed CDI/CDD, 2 sites (one southern wilaya). No real company names or logos in the app.
2. **Payroll engine + tests (§7)**, payslip PDF FR/AR, payroll card in Inbox.
3. **Compliance calendar + filing drafts (§8.3).**
3b. **MCP server (`tawzia_mcp`)** per Part B of `TAWZIA_BUSINESS_AND_MCP.md`: public legal/payroll tools first, then company read and draft tools. Agents in later stages call these tools.
4. **Employee Assistant + Documents agent** (attestation flow end to end).
4b. **Secure employee database (§8.5) + Registration & Onboarding agent (§6.6):** self-registration link, OCR verification, one approval card, parallel onboarding tasks, 30/60/90 check-ins, trial-period reminder, offboarding mirror. Sensitive-role steps last.
5. **Scheduler with CP-SAT (§8.2)**, reuse forecast model, Ramadan mode, swap flow.
6. **Recruiter + ANEM module + bias panel.**
7. **Ask Tawzia command bar** wired to all agent tools.
8. **Trust layer:** action log, PII redaction, "See why" on every card, settings for local model.
9. **Polish:** motion, empty states, FR/EN/AR (RTL for Arabic), mobile layout for the employee phone view.

Suggested stack (matches Anya's tools): Next.js + React + TypeScript + Tailwind front end; FastAPI back end importing the existing Python ML; OR-Tools; an LLM API with tool use (a fast model for routine calls, a stronger one for planning-heavy calls); SQLite/Postgres. If the jury date leaves no time for a front-end migration, keep Streamlit and apply sections 4 to 6 anyway: the 5-screen structure and the Inbox matter more than the framework.

## 10. Jury demo script (about 5.5 minutes, "a day where HR does nothing"; if capped at 5, shorten step 3 to 40 s)

1. **08:00, open Tawzia.** Inbox shows 6 cards. "Hours saved this month: 46h (estimate)." (20 s)
2. **Worker texts in Darija** for an attestation de travail → PDF appears → Approve → delivered. (40 s)
3. **"Ramadan starts Thursday, redo next week."** typed in Ask Tawzia → new schedule, 0 violations, stability score, one card explains a blocked night shift with art. 29 and how the derogation flag works. (70 s)
4. **Payroll card:** 142 payslips ready, 3 anomalies, one is overtime above the 20% cap, cited art. 31. Approve. G50 draft ready for the 20th. (60 s)
5. **Hiring:** ANEM countdown at day 4 of 5, candidates ranked with explanations, bias panel green. (50 s)
5b. **New hire registers from her phone** (show the phone mockup): ID photo → fields filled, blurry diploma bounced back automatically → HR approves one card → contract, CNAS draft, badge, laptop, first-week schedule all launch at once. Her role is marked sensitive, so the reference check and access review appear on their own, with no extra clicks. (45 s)
6. **Trust slide inside the app:** action log, PII redaction toggle, "every decision is human-approved." (30 s)
7. Close with the one-liner from §2. (10 s)

Be honest on stage: the forecast model is trained on simulated volumes with real Hijri and weather signals; it retrains on a client's own data at onboarding.

## 11. Things the build must NOT do
- Hardcode any rate from this file outside the config.
- Let any agent submit filings, send messages, or reject candidates without an Approve click.
- Call real external services (ANEM, CNAS, DGI portals) in the demo; link to them only.
- Use real company names, logos, or real people's data in seed data.
- Add pages beyond the five. New ideas become Inbox cards or command-bar actions. Two exceptions live outside the app: the public calculators on the landing site, and the public "verify a document" page reached from attestation QR codes (see growth loops in `TAWZIA_BUSINESS_AND_MCP.md`).
- Expose any approve, submit, send, pay, delete or reject action through the MCP server.

---

## Sources

Legal and payroll
- SNMG 24,000 DA from Jan 2026: [TSA](https://www.tsa-algerie.com/algerie-forte-revalorisation-du-salaire-minimum-et-de-lallocation-chomage/), [Algérie360](https://www.algerie360.com/salaire-minimum-la-hausse-du-a-24-000-da-officiellement-entree-en-vigueur/)
- Net salary calc, IRG brackets, CNAS 9/25/0.5: [UpGrowth 2026](https://www.upgrowth.dz/calcul-salaire-net-algerie-2026), [UpGrowth CNAS guide](https://www.upgrowth.dz/cnas)
- IRG lissage formulas: [Algérie360](https://www.algerie360.com/irg-salaires-exoneration-30000-da-abattements/)
- G50 and Jibaya'tic: [UpGrowth G50](https://www.upgrowth.dz/g50-declaration-algerie)
- DAS online, deadline 31 Jan: [Algérie-Eco](https://algerie-eco.com/?p=233782)
- Law 90-11 text (night work, overtime, rest, leave, trial, CDD, règlement intérieur): [WIPO Lex](https://www.wipo.int/wipolex/edocs/lexdocs/laws/fr/dz/dz039fr.html)
- Working hours, holidays, 40h ord. 97-03: [Africarrières](https://africarrieres.com/algeria/en/guide/droit-du-travail/working-hours-leave), [Africarrières labour code](https://africarrieres.com/algeria/en/guide/droit-du-travail/labor-code)
- Employer obligations summary: [Lamacta](https://lamacta.com/en/blog/droit-travail-algerie-2026-essentiel-employeurs/)
- ANEM 5 working days (law 20-03): [Emploitic blog](https://blog.emploitic.com/index.php/delai-de-traitement-de-loffre-demploi-par-lanem-et-organismes-de-recrutement-prives/); ANEM pain points: [TSA 2019](https://www.tsa-algerie.com/recrutement-comment-lanem-complique-la-vie-des-entreprises/)
- Ramadan 2026 public hours: [Algérie-Eco](https://algerie-eco.com/2026/02/16/ramadan-les-horaires-de-travail-dans-les-institutions-et-administrations-publiques-fixes/)
- PLF 2027: [Algérie-Eco](https://algerie-eco.com/2026/10/04/le-conseil-des-ministres-adopte-le-plf-2027-qui-prevoit-lintegration-des-augmentations-des-salaires/)
- Law 25-11 (data protection): [IT Solutions comparison](https://itsolutions.dz/loi-25-11-vs-18-07-algerie/), [official JO text](https://droit.mjustice.gov.dz/sites/default/files/loi_25-11-fr.pdf); biometric attendance deliberation: [TSA](https://www.tsa-algerie.com/algerie-le-pointage-biometrique-au-travail-est-il-legal/)

Registration, onboarding, e-signature
- CNAS affiliation of new employees (10 days, teledeclaration.cnas.dz, sécu 01, documents): [Legal Doctrine](https://legal-doctrine.com/edition/affiliation-des-nouveaux-salaries-a-la-cnas)
- Electronic signature and trust services law 26-02 (17 Feb 2026): [TSA](https://www.tsa-algerie.com/transactions-et-signature-electroniques-lalgerie-franchit-un-grand-pas/)
- Public bodies no longer requiring nationality certificate / bulletin n°3 in some cases (2020 decree): [TSA](https://www.tsa-algerie.com/dossiers-administratifs-deux-documents-ne-sont-plus-exigibles/)

Market, AI, evidence
- HR admin burden survey: [Eagle Hill via Trade & Industry Dev](https://www.tradeandindustrydev.com/industry/all-industries/survey-finds-hrs-problem-isnt-too-much-work-its-36409.md)
- HR agent landscape: [Darwinbox](https://darwinbox.com/blog/10-best-ai-agent-platforms-hr-teams), [HRpresso](https://hrpresso.com/blog/ai-agents-for-hr)
- EU AI Act deferral to 2 Dec 2027: [Cooley](https://cdp.cooley.com/digital-ai-omnibus-delays-key-deadlines-introduces-new-rules/)
- Stable scheduling RCT: [UChicago News](https://news.uchicago.edu/story/stable-scheduling-increases-sales-and-employee-productivity-study-finds)
- Algerian labour market (ONS Oct 2024): [Algérie360](https://www.algerie360.com/marche-du-travail-en-algerie-un-taux-de-chomage-en-hausse-et-des-inegalites-persistantes/)
- Competitors: [Talenteo (MEA Tech Watch)](https://meatechwatch.com/2025/07/02/algerian-startup-talenteo-develops-localized-hr-saas-platform-for-smes-with-regional-expansion-plans/), [Talenteo compliance guide](https://talenteo.com/en/conformite-rh-et-paie-algerie-2026-guide-complet/), [Almawarid](https://almawarid.app/blog/anem-algerie-obligations-des-employeurs-et-declaration-des-postes-vacants/)
