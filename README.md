# FlocCare GTM engine: NYC cardiology

An automated, trust-first outbound system that finds every independent cardiology practice in the five boroughs, names the decision-maker and a clinical champion, scores and tiers each account, writes a multichannel sequence in its patients' languages, reacts to opens, clicks, replies and silence, and flags sales-ready accounts with the reason why.

**Guardrail: nothing is sent to a real prospect.** Every email is addressed to a test inbox and written to `output/outbox/` as an `.eml` file; the clinic's name only appears in an `X-Intended-Recipient` header. See [Guardrail](#guardrail).

```bash
pip install -r requirements.txt
python run.py            # end to end on the cached public-data pulls (offline, about 10 s)
python run.py --live     # re-pull CMS, NPPES and Census live
python -m pytest -q      # guardrail + classifier tests
open output/dashboard.html
```

## What it produces (`output/`)

| File | What it is |
|---|---|
| `FlocCare_NYC_Cardiology_Top75.xlsx` | The 75 clinics with score breakdown, decision-maker, champion and language hook; every message; all 279 scored accounts; live funnel model; scoring logic; demo log; sources |
| `top75_clinics_scored.csv`, `top75_messages.csv` | Same, as CSV (707 messages) |
| `outbox/launch/day_+01/*.eml` | Day 1-2 emails for the 75, all to the test inbox |
| `outbox/*/tasks.jsonl` | Phone, LinkedIn, direct-mail and ad-audience steps as tasks |
| `demo/demo_timeline.md` | Eight scripted prospect behaviors and every decision the engine made |
| `alerts/` | Sales-ready alerts (Slack-style), each with the reason and an AE handoff draft |
| `sales_ready.csv`, `funnel.json`, `floccare_gtm.db` | Sales-ready list, funnel math, SQLite tracking (accounts, contacts, touches, events, decisions, alerts) |
| `dashboard.html` | Interactive console: the 75, the demo, a live simulator, the method |

## Why cardiology

| Option | Verdict |
|---|---|
| **Cardiology** | FlocCare already has a hypertension/CVD case study and a cardiology product page. Hypertension, AFib and heart failure are adherence problems where education changes outcomes. Cardiometabolic overlap ties straight into FlocCare's diabetes positioning. NYC has about 680 Medicare-billing cardiology sites, many in neighborhoods where 30-49% of households have limited English. |
| Fertility & IVF | FlocCare's strongest proof, but NYC has a few dozen IVF clinics in total. 75 new conversations a month would exhaust the market immediately. |
| Dental | Biggest universe, weakest fit: low-stakes education, DSO consolidation, no FlocCare proof. |
| Orthopaedics | Strong pre/post-op education need, but no FlocCare proof point and no language wedge. |
| Longevity | Small, cash-pay, marketing-led; tiny NYC universe. |

## How it works

| Stage | Module | What happens |
|---|---|---|
| Source | `engine/sources.py` | CMS Doctors & Clinicians file (every Medicare-enrolled clinician: specialty, group, group size, address, phone), NPPES registry (each organization's authorized official), Census ACS 2020-24 table C16002 (household language, limited-English households by ZIP). Free, public, no list-building. |
| Enrich | `engine/enrich.py` | One account per practice (a 3-office group is one account with 3 sites). Excludes imaging-only, pediatric and telehealth entities; routes hospital systems (NYU, Mount Sinai, Columbia, Montefiore, Northwell, Weill Cornell, MSK and others) to an enterprise motion. Decision-maker = NPPES authorized official with an owner/operations title, else the physician named on the entity, else the most senior cardiologist in a small cardiology group. Champion = the most recently trained cardiologist who isn't the decision-maker. One person, one sequence (dedupe across practices). |
| Prioritize | `engine/score.py` | 100 points, every point from a sourced field, plus a written reason per account (below). |
| Engage | `engine/messages.py`, `config/sequence.yaml` | Writes every step and every reactive reply per account. Personalization = practice, people, street, ZIP language data, service line. Clinical content lives in a fixed set of sample assets (5 topics x N languages, clinician-reviewed before launch), so nothing medical is improvised per clinic. In this demo the links open the drafts in [`samples/`](samples/); in production each is a tracked short link per account and channel. |
| React | `engine/reactor.py`, `config/rules.yaml` | Day-by-day engine. Events add engagement points and fire actions; silence escalates the channel. Deterministic: same inputs, same decisions. |
| Surface | `engine/reactor.py` | Sales-ready on a positive reply or interested call, on engagement >= 35 for Tier A/B, or when two people at the practice engage. Writes an alert with the reason and an AE draft. |
| Report | `engine/report.py` | Workbook, CSVs, demo log, dashboard. |

## Scoring logic (and why)

| Block | Signal | Points | Why |
|---|---|---|---|
| Fit 35 | Segment: independent cardiology / community health center / small multispecialty / large multispecialty | 15 / 11 / 9 / 5 | Owner-run practices decide in one meeting. Hospital systems buy centrally and go to an AE. |
| | Cardiologists at the account: 1 / 2-3 / 4-9 / 10-20 / 21+ | 5 / 9 / 12 / 10 / 6 | Enough volume to feel the education load, small enough to decide fast. |
| | Sites: 1 / 2 / 3+ | 0 / 5 / 8 | Keeping material consistent across sites is a real pain. |
| Need 35 | Limited-English households at the primary ZIP: 30%+ / 20-30 / 12-20 / 6-12 / under 6 | 20 / 16 / 11 / 6 / 2 | Multilingual education is FlocCare's sharpest edge; NYC averages 14% limited-English households and half speak another language at home (ACS 2020-24). |
| | Service line: rhythm / prevention / heart+vascular / general / cardiometabolic | 10 / 9 / 8 / 7 / 6 | AFib anticoagulation and prevention are the most education-heavy. |
| | One language group >= 15% of households | +5 | A concrete hook for the outreach. |
| Timing 10 | Cardiologists trained 2010 or later: half+ / some / none | 10 / 6 / 3 | Adoption propensity. |
| Reach 20 | Decision-maker NPPES-named / inferred / unknown | 10 / 6 / 2 | A named person beats a guess. |
| | Champion distinct / same person / unknown | 5 / 3 / 0 | Two threads into a practice. |
| | Direct phone (NYC area code) | 5 | Small practices run on the phone. Out-of-area numbers in CMS are usually billing lines: flagged "verify" and scored 0. |

Tiers: A >= 70 (every channel, including printed mail and two calls), B >= 55 (email, LinkedIn, one call), C below (email + ads). All weights are in `config/settings.yaml`.

## Channels and sequence

Familiarity first, give before asking, a person on the phone, paper on the desk, then one clear ask.

| Day | Channel | Tiers | Why it earns trust |
|---|---|---|---|
| -7 | Ads audience (LinkedIn Matched Audiences, Meta) | A B C | They see the name next to free, useful content before any email arrives |
| -5 | LinkedIn connect, no pitch | A B | A face before an inbox |
| 1 | Email to decision-maker | A B C | A free one-page handout in their patients' languages with their name on it. No patient data, no login, an easy no |
| 2 | Email to clinical champion | A B | Asks for a clinician's critique, not a meeting |
| 3 | Call the practice | A B | Goal is a name and an address, not a pitch |
| 5 | Two-line bump (skipped if they clicked) | A B C | |
| 7 | Printed packet (Lob) with QR | A | Tangible, rare, gets past the front desk |
| 9 | LinkedIn message (only if accepted) | A B | |
| 12 | Proof email + first explicit ask | A B C | Cardiology case study, framed honestly |
| 15 | Follow-up call | A | Did the packet arrive? Book on the spot |
| 21 | Close + opt-in | A B C | No newsletter they didn't ask for |

## Reactions (`config/rules.yaml`)

| Signal | What the system does |
|---|---|
| Open | 2 points. Opens are mostly machine-generated now (Apple Mail Privacy Protection is over half of opens), so only 3+ opens in 48 h move anything: the next call is pulled forward. |
| Click on the sample | Same-day reply from a person, call next business day, bump cancelled |
| QR scan from the mailed packet | Follow-up, AE notified if over threshold |
| Reply: yes | Stop automation, sales-ready, AE draft |
| Reply: talk to X | Add X, intro email with the referrer's name |
| Reply: we already have handouts | Answer once (side-by-side offer), pause 5 days |
| Reply: not now | Acknowledge, snooze 60 days |
| Reply: remove me | Suppress on every channel |
| Out of office | Shift the rest of the sequence past the return date |
| Bounce | Mark invalid, phone and mail carry it, re-enrich |
| Silence | Next step is a different channel by design; after Day 21, nurture and re-enter at Day 111 or on a trigger |

Replies are classified by `classify_reply()` (rules here; an LLM with a confidence threshold and a human queue in production).

## Guardrail

1. `Outbox.build()` always puts the test inbox in `To`; the prospect goes in `X-Intended-Recipient`.
2. `Outbox._enforce()` raises `GuardrailViolation` if any To/Cc/Bcc is not the test inbox.
3. `smtp_sandbox` mode refuses to start unless `SMTP_HOST` is allowlisted (Mailtrap, localhost). `gmail_drafts` only creates drafts addressed to the test inbox.
4. The committed test inbox is a placeholder (`floccare-test-inbox@example.com`). To get the test emails in your own inbox, run `FLOCCARE_TEST_INBOX=you@example.com python run.py`.
5. `tests/test_guardrail.py` checks all of the above and scans every generated `.eml`.

## Funnel math

`engine/funnel.py` and the workbook's Funnel sheet (blue cells are editable assumptions):

- 279 outreach-eligible independent accounts (41 A, 126 B, 112 C). At 20% / 11% / 4% P(conversation) per full sequence, one pass yields about 27 first conversations.
- About 309 hospital-system cardiology sites at 5% (enterprise route) add about 15; a 90-day recycle at half rate adds about 12; referrals about 2.
- **Total: about 56 first conversations from the whole NYC cardiology market, under one month of a 75/month target.** Holding 75 a month needs about 789 fresh accounts a month at the blended rate.
- So the engine is config-driven: the same code runs cardiometabolic-adjacent specialties in NYC (endocrinology, nephrology) and then metro cardiology (Long Island, Westchester, North Jersey) by changing `config/settings.yaml`.
- Check on the assumptions: published cold-email benchmarks put the average reply rate around 3.4% and interested replies under 1% per email, so a 20% Tier A conversation rate leans on phone, mail and multi-threading. Even at double these rates, NYC cardiology covers under two months.
- The 75-account cohort run (seeded random behavior) produced 11 sales-ready accounts, in line with the tier assumptions.

## Going to production

| Here | Production |
|---|---|
| Cached pulls in `data/raw` | Nightly `--live` pull; CMS refreshes monthly |
| `email_status: needs enrichment` | Apollo / Hunter / Crustdata person-contact API on the decision-maker and champion; verify before send |
| `.eml` files | Mailtrap sandbox, then a warmed sending domain with SPF/DKIM/DMARC |
| Tasks file | Dialer (call tasks), Lob API (mail), LinkedIn Matched Audiences + Meta custom audiences (ads) |
| Simulated events | Webhooks from the sending tool (open, click, reply, bounce) and short-link/QR redirects into `apply_event()` |
| Rule-based reply classifier | LLM classifier with confidence threshold and human review |
| SQLite | Postgres + CRM sync (HubSpot/Salesforce) with the sales-ready alert into Slack |

The same logic maps one-to-one to n8n or Make if a no-code runtime is preferred: one workflow per stage, `rules.yaml` as a lookup table.

## Honest limitations

- Emails aren't in public data; the 75 need enrichment before any real send.
- NPPES authorized officials can be stale; first call verifies. Owners of cardiology practices are greeted as "Dr."
- Language labels below the Census family level (for example Russian vs Polish within "other Indo-European") come from a curated ZIP table, `config/nyc_zip_context.csv`.
- FlocCare's case-study outcome figures are framed on its site as industry evidence, so the messages cite the case study without quoting numbers.
- Behavior in the demo and cohort runs is simulated; conversion rates are assumptions to replace with real data in week one.

Data: CMS Doctors & Clinicians (data.cms.gov, dataset mj5m-pzi6), NPPES NPI Registry, Census ACS 2020-24 5-year (C16002, via Census Reporter), pulled 2026-11-23.
