# Tawzia: business model, growth engine, and MCP server

Companion to `TAWZIA_REBUILD_BRIEF.md`. Part A is for Anya, the pitch, and investors. Part B is a build spec for the coding agent.

Research date: 28 October 2026. Market figures are sourced at the bottom. Anything labelled **hypothesis** is a starting guess to test with real customers, never a claim to put on a slide as fact.

---

# PART A: The business

## A1. The honest starting point

- Today Tawzia is a prototype. To raise money it needs a legal company, a few real users, and proof that someone pays.
- No product guarantees new clients. What we can build is a business where (1) each client brings the next one, (2) leaving gets harder every month a client stays, and (3) the cost of serving a client falls over time. Every decision below serves one of those three.

## A2. Market (bottom-up, Algeria only)

- **1.32 million SMEs** employing **3.22 million salaried workers** (end of June 2022, Ministry of Industry data via Algérie-Eco). About **98% are micro-firms** under 10 employees.
- So roughly **26,000 firms with 10 to 249 employees** (2% of 1.32M, rough estimate). These are the core buyers: big enough to have payroll pain, small enough to have no HR software team.
- Plus large public and private groups (airports, banks, Sonelgaz-type companies, hospitals). Slow to buy, large contracts.
- Plus the micro-firms, reached **through their accountants** (see A5), since they won't buy software alone.
- Plus **embassies, international organisations and foreign companies** in Algiers that hire Algerian local staff and need Algerian payroll, CNAS handling and careful onboarding, often run by English-speaking admin teams. Small segment by count, high value per client, and a credibility signal for every other buyer. They're served by the normal product: English interface setting plus sensitive-role onboarding (rebuild brief §6.6). Nothing in the product or demo is labelled for them; this segment is for the sales plan only.
- Every one of these employers files the same G50, CNAS and DAS paperwork. The pain is universal and legally mandatory, which is the best kind of pain to sell against.

Illustrative sizing for the pitch (label it as illustrative): if Tawzia ends up serving 1 million employees at an average 250 DA per employee per month, that's 3 billion DA of annual recurring revenue. Show the formula on the slide so the jury sees the logic, and keep the inputs editable.

## A3. Competition and our lane

| Player | What they are | Gap we use |
|---|---|---|
| Talenteo (Algiers, 2022, funded by 216 Capital in 2025) | HR/payroll SaaS for SMEs under 250 staff, has an accountant partner program | Coverage shows no AI agents. They digitize forms; we do the work |
| Almawarid (Oran) | Broad SME management suite incl. payroll, offline desktop app, free plan | Generalist; no agentic layer, no scheduling optimizer |
| CODEV LogistiQ ERP | ERP with HR/payroll module | ERP buyers, heavy implementation |
| Excel + a payroll clerk | The real incumbent | Error-prone, depends on one person, no legal alerts |
| Workday / SAP / Oracle | Global suites with HR agents | Don't know Algerian law, priced for multinationals, data leaves the country |
| Cercli (UAE, $4M seed 2024), Bluworks (Egypt, $1M seed Dec 2025) | Regional HR/payroll players | Prove investors fund MENA payroll and frontline HR. Neither covers Algeria today as far as I found |

**Positioning line:** *Tawzia is the agentic HR layer built on Algerian law. Others give you software to do HR. Tawzia does HR and asks for your signature.*

## A4. Revenue model (hypotheses to test with the first 5 customers)

Local pricing reality: Stripe doesn't operate in Algeria and PayPal has withdrawn; local SaaS bills through bank transfer, CCP, Baridi Mob and Algerian card rails, at roughly a tenth of international prices. Invoice in dinars, prefer annual prepayment with a discount (cash flow + lower churn).

| Plan | Who | Price (hypothesis) | Includes |
|---|---|---|---|
| **Essentiel** | 10 to 49 employees | 300 DA / employee / month, minimum 6,000 DA | Payroll agent, filings calendar + drafts, documents, employee assistant |
| **Opérations** | Shift-based firms | + 200 DA / employee / month | Scheduler agent (CP-SAT, Ramadan mode, swaps), demand forecast |
| **Entreprise** | 250+ / public groups | Annual contract, quote | Local or on-premise hosting, SSO, custom rules, SLA |
| **Cabinet** (accountants) | Accounting firms | Per client file, volume tiers | Multi-company console, white-label payslips |
| **Setup fee** | All paid plans | One-off | Data migration from Excel/old software, leave-balance import |

Sanity check for the sales conversation: a 50-employee firm on Essentiel pays 15,000 DA a month, well under the monthly cost of one payroll clerk, and Tawzia never takes leave during DAS season. Use real salaries from interviews to rebuild this comparison; don't invent them.

**Later revenue (only after traction, some need licences):**
- Verified attestations for banks (see A5 loop 2): banks may pay per verification.
- Aggregated, anonymised salary benchmarks (opt-in only, law 25-11 compliant).
- Earned wage access / salary advances: regulated, needs a financial partner. Mention as a vision line, never as a near-term plan.

## A5. The growth engine: 5 loops that keep bringing clients

**Loop 1: Accountants (the biggest one).** Many Algerian SMEs outsource payroll to a cabinet comptable. One accountant brings many client files. Give accountants a multi-company console where the agents prepare every client's payroll and G50 draft, and the accountant just reviews. More clients = more profit for them with the same staff. They recruit companies for us. Talenteo already courts accountants, so our edge must be visible in the first demo: "your 40 client payrolls done by the 20th, you only approve."

**Loop 2: Verified documents (product-led virality).** Every attestation de travail / de salaire Tawzia issues carries a QR code and a short verification link ("Vérifié par Tawzia"). Banks, landlords, embassies and visa centres scan it. Every scan shows Tawzia to someone who decides on credit or hiring, and to the employee's next employer. Free for the verifier, so it spreads.

**Loop 3: Free tools that rank and capture leads.** Public calculators: net salary (with the 2026 IRG rules), employer cost, overtime legality, "is this night shift legal?", the monthly compliance calendar by email. People search these every January (new finance law) and every month before the 20th. Each tool ends with "Let Tawzia's agents do this for your whole company." The MCP server (Part B) puts the same tools inside the AI model and other AI assistants, so people asking an AI about Algerian payroll land on Tawzia too.

**Loop 4: Employees carry Tawzia to their next job.** Workers use the assistant for payslips, leave and attestations. When they change companies, they ask HR: "why don't you have Tawzia?" Make it easy: a referral link in the employee app ("Recommend Tawzia to your new employer").

**Loop 5: The law changes every January, and we absorb it.** Each finance law, SNMG change or new decree is an emergency for companies on Excel or old software. For Tawzia clients it's a config update and an Inbox card: "IRG rules updated for 2027, your January payroll already uses them." Run a webinar every January ("Ce que la LF change pour votre paie") as the main acquisition event of the year.

## A6. Why clients stay (retention and moat)

- **Accumulated history:** payslips, leave balances, DAS history, contracts, action log. Leaving means migrating years of legally relevant records.
- **Trained models per client:** the demand forecast and scheduler learn each client's patterns. Month 12 is better than month 1.
- **Legal-rules engine with dated configs:** every rule is versioned with its source. This is slow, careful work competitors have to redo.
- **Workflow lock-in through employees:** once 140 workers request leave and documents through the assistant, switching off Tawzia is felt across the whole company.
- **Data residency as a feature:** law 25-11 and the 2025 data governance decree push toward local hosting. Offer Algerian hosting and a local-model option from day one; it's a sales argument big buyers can't get from foreign suites.

Track these monthly: logo churn, net revenue retention (expansion from modules and headcount growth), employees under management, % of payrolls approved with zero edits (the "trust" metric), hours saved per client.

## A7. Funding path (in order)

1. **Incorporate** (SARL or EURL). Per the startup decree as summarised by UpGrowth, individuals and auto-entrepreneurs don't qualify for the startup label, though one 2026 article says labelled self-employed founders get the tax exemptions. Check with Algeria Venture which applies to you.
2. **Startup label on startup.dz:** company under 8 years old, under 250 employees, innovative model. Committee answers within 30 days. Benefits: 4 years exemption from IRG/IBS/IFU, renewable 2 more years (2026 Finance Law arts. 100-101 + DGI circular 15), and priority access to the **Algerian Startup Fund (ASF)**.
3. **3 to 5 design partners** with signed pilot agreements (warm leads already exist from your earlier outreach to an airport and a bank; one shift-based, one office-based, one accountant would be ideal).
4. **First 10 paying companies + 3 accountant partners.** This is the seed story.
5. **Seed round:** ASF, regional VCs that already fund MENA HR/payroll (the investors behind Bluworks and Cercli show the thesis exists), plus 216 Capital-style North African funds. PLF 2027 adds 10-year tax exemptions for investors in venture funds (SICAR/FCPR), which may make local VC money easier to raise from 2027; it's still a bill.
6. **Regional expansion pack:** Tunisia and Morocco share French-heritage payroll structures; the dated-config rules engine is built so a new country is a new config + legal corpus.

**Team gap to fix before a seed round:** investors will ask who sells and who knows payroll. A co-founder or advisor with HR/payroll or accounting credibility in Algeria matters as much as the code.

## A8. Investor pitch structure (10 slides)

1. Problem: Algerian HR is legally heavy, manual, and depends on one clerk (Eagle Hill admin stats + the G50/CNAS/DAS/ANEM calendar).
2. Demo GIF: worker asks in Darija → attestation in 20 seconds.
3. Product: Approval Inbox + 6 agents.
4. Why now: agents went mainstream globally in 2025-26 (Workday, SAP, Oracle); Algeria made online filing mandatory (Jibaya'tic 2026, 80%+ CNAS e-declaration); law 25-11 favours local players.
5. Market: bottom-up formula (A2).
6. Business model: per-employee SaaS + modules + accountants (A4).
7. Growth loops (A5) as one diagram.
8. Moat and retention (A6).
9. Traction: design partners, pilots, hours saved, payroll accuracy. Real numbers only.
10. Team, ask, use of funds.

## A9. 90-day go-to-market plan

**Goal (SMART):** by end of January 2027, 3 signed design partners, 10 accountant firms trialling the Cabinet console, 1,000 monthly users of the free calculators.

**Audience profile:** *DRH or payroll manager at an Algerian company of 20 to 300 people, often shift-based, who loses days every month to payroll, G50 and CNAS paperwork and fears a CNAS penalty. They discover tools through LinkedIn, Facebook HR/compta groups, their accountant, and word of mouth, and care most about legal safety and time.*

**Core message:** *Vos agents RH font la paie, les déclarations et les plannings. Vous signez.*

Supporting messages:
1. Zero missed deadline: G50, CNAS, DAS prepared before you think of them. (Proof: calendar demo)
2. Every number cites the law. (Proof: article shown on each card)
3. Your workers get answers in Darija in seconds. (Proof: attestation demo)
4. Your data stays in Algeria. (Proof: local hosting, law 25-11 design)

**Channels**

| Channel | Why | Effort |
|---|---|---|
| Direct outreach to design partners (email + in-person) | Fastest path to real usage | High |
| Accountants (ONECCA network, local cabinets) | Loop 1 multiplier | High |
| LinkedIn (Anya + Tawzia page), FR/AR | DRH and founders are there | Medium |
| Facebook HR & comptabilité groups | Where Algerian payroll questions get asked | Low |
| Free calculators + SEO pages | Loop 3, compounds over time | Medium |
| January finance-law webinar | Peak-intent moment of the year | Medium |
| Embassy jury + startup events | Credibility and PR | Medium |

**Calendar**

| Week | Content / action | Channel | Notes |
|---|---|---|---|
| 1-2 | Landing page FR/AR/EN + net-salary calculator live | Website | Must exist before any posting |
| 1-2 | Shortlist 15 design-partner targets, 20 accountant firms | Direct | Start with warm leads |
| 3 | Post: "Combien coûte vraiment un salarié en 2026 ?" with calculator | LinkedIn, FB groups | |
| 3-4 | Design-partner meetings, 20-min live demo | In person | Sign pilot agreements |
| 4 | Overtime + night-shift legality checker live | Website, MCP | |
| 5 | Embassy jury presentation | Event | Film it; reuse clips |
| 6 | Accountant console beta, 3 firms | Direct | |
| 6-8 | Weekly post: one law article explained in 60 seconds (video) | LinkedIn, FB, TikTok | Batch-record |
| 8 | Monthly compliance-calendar email starts | Email | Sign-ups from calculators |
| 9-10 | Webinar invite: "Loi de finances 2027 : ce qui change pour la paie" | All | Depends on LF 2027 publication |
| 11 | Webinar | Online | Convert to pilots |
| 12 | Case study from first design partner (real numbers) | All | Only with their written OK |

**KPIs:** primary = signed design partners (target 3). Secondary: accountant trials (10), calculator monthly users (1,000), webinar registrations (150), demo-to-pilot rate. Review weekly.

**Risks and mitigations**
- *Big buyers trust foreign brands* → start with SMEs and accountants; use the embassy jury and pilots as credibility.
- *Payroll error damages trust* → every rule tested against published examples, human approval on every run, parallel run with the client's old method for the first 2 months.
- *Competitor adds AI* → speed + depth on Algerian rules + accountant console + verified-document loop.
- *LLM data leaving Algeria* → PII redaction, local hosting, local-model option.
- *Founder is still a student* → recruit a payroll/accounting co-founder or advisor early; be upfront about it.

---

# PART B: MCP server spec (for the coding agent)

## B1. Why an MCP server

One tool layer, three users:
1. **Tawzia's own agents** call these tools (no duplicated logic between the app and the agents).
2. **Accountants and HR managers** connect Tawzia to the AI model (or any MCP client) and ask "prepare November G50 drafts for all my clients."
3. **The public**: free, read-only legal and payroll tools anyone's AI assistant can call. This is growth loop 3 and a distribution channel nobody in Algeria has claimed.

Safety rule carried over from the brief: **MCP tools can read, calculate and create drafts or Inbox cards. They never approve, file, pay, send or reject.** Approvals happen in the Tawzia app by a human.

## B2. Stack and structure

- Python, **FastMCP** (the back end is already Python and the payroll engine lives there). Server name: `tawzia_mcp`.
- Transport: **Streamable HTTP**, stateless JSON, for the hosted server; stdio build for local testing with MCP Inspector.
- Read the mcp-builder skill's Python guide (`reference/python_mcp_server.md`) and the Python SDK README before coding.
- The tools import the same modules as the app: `payroll_engine`, `rules` (dated YAML configs), `law_corpus`, `scheduler`, `calendar_dz`.
- Two scopes on one server:
  - **public** tools: no auth, rate-limited, read-only.
  - **company** tools: OAuth 2.1 bearer token scoped to one company (accountants get a token per client or a cabinet token listing clients).
- Every tool: Pydantic input model with constraints and examples, `response_format` (`markdown` default, `json`), annotations, actionable error messages, pagination on lists (`limit` default 20, `has_more`, `next_offset`, `total_count`).
- Every legal result returns `sources`: article number + text id + config version (`dz_payroll_2026@2026-01-01`).
- Every company-scope call is written to the action log (who, tool, args hash, time).
- PII redaction applies to any tool output that would go to an external LLM in the hosted agents.

## B3. Public tools (read-only, `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: false`)

| Tool | Input | Output |
|---|---|---|
| `tawzia_calculate_net_salary` | gross, pay items with `cnas_subject`/`irg_subject`, worker_status (`standard`/`disabled`/`retired`), period | CNAS, taxable, IRG steps (barème, abattement, lissage), net, sources |
| `tawzia_calculate_employer_cost` | gross, items, headcount | employer CNAS by branch, total cost, config version |
| `tawzia_check_overtime` | contract hours, hours worked per day for a week, hourly wage | legal/illegal, cap usage vs 20%, minimum premium due (≥50%), articles 31-32 |
| `tawzia_check_shift_legality` | shift start/end, worker age, worker gender, site has women night-work derogation, weekly rest day | violations list with articles 27, 28, 29, 33, 36 |
| `tawzia_get_compliance_calendar` | month, headcount, tax regime | deadlines (G50, CNAS, DAS, etc.) with dates adjusted for weekends/holidays and sources; items marked `verify` where the brief does |
| `tawzia_get_public_holidays` | year | fixed + Hijri holidays with estimated dates and a note that Hijri dates are confirmed by official announcement |
| `tawzia_check_cdd_validity` | reason, start, end, renewals | valid case under art. 12 or not, explanation |
| `tawzia_search_labour_law` | query, limit | matching articles (law 90-11, 20-03, 25-11 summaries) with ids and short text |
| `tawzia_explain_payslip_line` | line code | plain-language explanation FR/AR/EN |

## B4. Company tools (OAuth, company-scoped)

Read tools (`readOnlyHint: true`):
- `tawzia_list_employees` (filters: site, contract type, status; paginated)
- `tawzia_get_employee` (profile, contract, leave balance; sensitive fields only with the right scope)
- `tawzia_list_inbox_cards` (status filter, paginated)
- `tawzia_preview_payroll` (month → totals, anomalies, per-employee lines; computes, saves nothing)
- `tawzia_get_filing_draft` (type: `g50_irg` / `cnas_monthly` / `das`, period)
- `tawzia_get_schedule` (site, week)
- `tawzia_list_open_positions`, `tawzia_get_candidate_ranking` (with explanations and bias-panel figures)

Draft tools (`readOnlyHint: false`, `destructiveHint: false`, `idempotentHint: false`). Each creates an **Inbox card** awaiting human approval and returns its id:
- `tawzia_draft_document` (type: attestation de travail / de salaire / certificat de travail, employee id, language)
- `tawzia_draft_schedule` (site, week, constraints overrides such as Ramadan hours)
- `tawzia_draft_leave_decision` (request id, decision suggestion)
- `tawzia_draft_job_post` (brief, language)
- `tawzia_draft_payroll_run` (month)
- `tawzia_draft_registration_invite` (candidate id, start date, role checklist) → card; HR approves before the link is sent
- `tawzia_draft_offboarding` (employee id, last day, reason)

Onboarding read tools (`readOnlyHint: true`):
- `tawzia_get_onboarding_status` (employee id → checklist progress, missing documents, overdue tasks, trial-period end date; sensitive fields never returned, only "present / verified / missing")
- `tawzia_list_upcoming_trial_ends` (days ahead; paginated)

Accountant tool:
- `tawzia_list_client_companies` (cabinet scope; paginated, with each client's next deadline and open cards)

Deliberately absent: any approve, submit, send, pay, delete or reject tool.

## B5. Evaluations (create `evaluations/tawzia_mcp_eval.xml`)

Follow the mcp-builder evaluation guide: 10 questions, read-only, multi-step, one stable verifiable answer each, run against the seeded fictional company. Examples to include (answers must be computed from the seed data and verified before saving):
- "Net salary for a standard employee with 35,000 DA taxable income?" (expect IRG 2,070)
- "Which employees at the southern site are scheduled on a night shift next week in violation of art. 29, and what is the site's derogation status?"
- "How many working days remain before the G50 deadline for October's payroll if today is 14 November 2026?"
- "Which employee has the highest overtime this month, and is it within the 20% cap?"

## B6. Build steps (add to the rebuild brief's order after stage 3)

1. Extract payroll, rules, calendar and law-search into importable modules if they aren't already.
2. Public tools + unit tests reusing the payroll test vectors.
3. Company read tools, then draft tools, behind OAuth.
4. Switch the in-app agents to call the MCP tools.
5. Evaluations file.
6. Public listing page on the landing site ("Use Tawzia's legal tools inside your AI assistant") with setup instructions; submit to MCP registries once stable.

---

## Sources

- SMEs and jobs (end June 2022): [Algérie-Eco](https://algerie-eco.com/2023/02/18/algerie-plus-de-13-million-de-pme-jusqua-fin-juin-2022/)
- Algerian B2B SaaS, payments, data residency decree 25-320: [AlgeriaTech, Apr 2026](https://algeriatech.news/algeria-saas-startups-b2b-enterprise-software-wave-2026/)
- Startup label criteria and benefits: [UpGrowth](https://www.upgrowth.dz/comment-obtenir-label-startup-algerie); 2026 Finance Law startup exemptions: [AlgeriaTech](https://algeriatech.news/?p=21816)
- PLF 2027 investor incentives: [IT Mag](https://www.itmag.dz/2026/10/14/plf-2027-br-lalgerie-mise-sur-la-fiscalite-pour-drainer-lepargne-vers-les-start-up/)
- Talenteo: [MEA Tech Watch](https://meatechwatch.com/2025/07/02/algerian-startup-talenteo-develops-localized-hr-saas-platform-for-smes-with-regional-expansion-plans/), [Talenteo guide](https://talenteo.com/en/conformite-rh-et-paie-algerie-2026-guide-complet/)
- Almawarid: [Almawarid](https://almawarid.app/blog/anem-algerie-obligations-des-employeurs-et-declaration-des-postes-vacants/)
- Cercli seed: [Techeconomy](https://techeconomy.ng/cercli-aims-to-disrupt-mena-payroll-market-with-4-million-funding/); Bluworks seed: [SceneNow](https://www.scenenow.com/Business/Bluworks-Raises-1M-Led-by-A15-Enza-Capital-Beltone-VC)
- CNAS e-declaration adoption: [Algérie-Eco](https://algerie-eco.com/?p=233782); Jibaya'tic mandatory 2026: [UpGrowth G50](https://www.upgrowth.dz/g50-declaration-algerie)
- HR admin burden: [Eagle Hill survey](https://www.tradeandindustrydev.com/industry/all-industries/survey-finds-hrs-problem-isnt-too-much-work-its-36409.md)
- Legal sources for the tools: see `TAWZIA_REBUILD_BRIEF.md`
