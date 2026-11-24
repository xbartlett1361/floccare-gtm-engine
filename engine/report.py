"""Write every output a reviewer needs: CSVs, an Excel workbook, the demo timeline, the dashboard."""
from __future__ import annotations

import json

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .util import ROOT, load_yaml

OUT = ROOT / "output"
ARIAL = "Arial"
HDR = PatternFill("solid", fgColor="1F3A5F")
BLUE = Font(name=ARIAL, color="0000FF")


def top_row(a: dict) -> dict:
    s = a["subscores"]
    ch = a["champion"]
    return {
        "Rank": a["rank"], "Practice": a["practice"], "Account ID": a["id"], "Tier": a["tier"],
        "Fit (35)": s["fit"], "Need (35)": s["need"], "Timing (10)": s["timing"], "Reach (20)": s["reach"],
        "Score (100)": a["score"], "Why this score": a["score_reason"],
        "Segment": a["segment"].replace("_", " "), "Borough": a["borough"], "Neighborhood": a["neighborhood"],
        "Primary site": f"{a['primary'].get('street_full', '')}, {a['zip']}", "Sites": a["n_sites"],
        "Phone": a["phone_display"] + (" (out of area: verify)" if a.get("phone_note") else ""),
        "Cardiologists": a["n_cardiologists"],
        "Decision-maker": a["dm"]["name"], "DM title": a["dm"]["title"],
        "DM source": {"registry": "NPPES authorized official", "unknown": "to enrich"}.get(
            a["dm"]["source"], a["dm"].get("inferred_how", "inferred")),
        "Clinical champion": f"Dr. {ch['name']}" if ch else ("same as DM" if a["champion_status"] == "same_as_dm"
                                                             else "to find on first call"),
        "Champion basis": ch["why"] if ch else "",
        "Limited-English households % (ZIP)": a["lep_pct"], "Non-English households % (ZIP)": a["non_english_pct"],
        "Language hook": a["language"] or "none (English materials + plain language)",
        "Sample handout topic": a["topic"], "Email status": a["email_status"],
    }


def _style_sheet(ws, widths: dict | None = None, wrap_cols: set | None = None):
    for c in ws[1]:
        c.font = Font(name=ARIAL, bold=True, color="FFFFFF")
        c.fill = HDR
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name=ARIAL, size=10, color=c.font.color.rgb if c.font and c.font.color and
                          c.font.color.type == "rgb" else None)
            c.alignment = Alignment(wrap_text=bool(wrap_cols and c.column_letter in wrap_cols), vertical="top")
    ws.freeze_panes = "C2"
    for i, col in enumerate(ws.columns, 1):
        letter = get_column_letter(i)
        ws.column_dimensions[letter].width = (widths or {}).get(letter, 16)


def write_workbook(top: list[dict], all_accounts: list[dict], messages: list[dict], funnel: dict,
                   demo: list[dict], cfg: dict) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Top 75"
    rows = [top_row(a) for a in top]
    cols = list(rows[0])
    ws.append(cols)
    for i, r in enumerate(rows, start=2):
        vals = [r[c] for c in cols]
        ws.append(vals)
        # score is a live formula over the four subscores (E:H)
        ws.cell(row=i, column=cols.index("Score (100)") + 1, value=f"=SUM(E{i}:H{i})")
    _style_sheet(ws, {"A": 6, "B": 34, "C": 17, "D": 6, "E": 8, "F": 9, "G": 9, "H": 9, "I": 9, "J": 60,
                      "N": 30, "R": 24, "S": 22, "T": 30, "U": 24, "V": 30, "Y": 22, "Z": 44, "AA": 30},
                {"J", "T", "V", "Z"})

    ws = wb.create_sheet("Messages (Top 75)")
    mcols = ["practice", "account_id", "step", "day", "channel", "to_name", "to_role", "condition", "subject", "body"]
    ws.append([c.replace("_", " ").title() for c in mcols])
    for m in messages:
        ws.append([m[c] for c in mcols])
    _style_sheet(ws, {"A": 30, "B": 17, "C": 15, "D": 6, "E": 11, "F": 24, "G": 22, "H": 18, "I": 44, "J": 90},
                 {"I", "J"})

    ws = wb.create_sheet("All accounts scored")
    acols = ["rank", "practice", "id", "route", "tier", "score", "segment", "borough", "neighborhood", "n_sites",
             "n_cardiologists", "lep_pct", "language", "score_reason"]
    ws.append([c.replace("_", " ").title() for c in acols])
    for a in sorted(all_accounts, key=lambda a: (a.get("rank") or 9999)):
        ws.append([a.get(c) if c != "score_reason" else (a.get("score_reason") or a.get("exclude_reason"))
                   for c in acols])
    _style_sheet(ws, {"B": 34, "C": 17, "N": 70}, {"N"})

    # ---- Funnel with live formulas; blue = editable assumption
    ws = wb.create_sheet("Funnel")
    p = funnel["p_by_tier"]
    f = cfg["funnel"]
    lines = [
        ("Assumption / step", "Value", "Note"),
        ("Target first conversations per month", funnel["target_per_month"], "From the brief"),
        ("Tier A accounts", funnel["tiers"]["A"], "Scored universe, this repo"),
        ("Tier B accounts", funnel["tiers"]["B"], ""),
        ("Tier C accounts", funnel["tiers"]["C"], ""),
        ("P(conversation) Tier A", p["A"], "Full multichannel sequence incl. phone + mail"),
        ("P(conversation) Tier B", p["B"], "Email + LinkedIn + one call"),
        ("P(conversation) Tier C", p["C"], "Email + ads only"),
        ("Expected conversations, first pass", "=B3*B6+B4*B7+B5*B8", "Formula"),
        ("Blended conversion rate", "=B9/SUM(B3:B5)", "Formula"),
        ("Hospital-system cardiology sites (CMS)", funnel["health_system_sites"], "CMS sites minus independent sites"),
        ("P(conversation) per system site", f["p_conversation_health_system_site"], "Site-level champion, enterprise route"),
        ("Expected system-site conversations", "=B11*B12", "Formula"),
        ("Recycle multiplier (pass 2 at 90 days)", f["recycle_multiplier"], ""),
        ("Expected recycle conversations", "=(B3*(1-B6)*B6+B4*(1-B7)*B7+B5*(1-B8)*B8)*B14", "Formula"),
        ("Referral intros per conversation", f["referral_rate_per_conversation"], ""),
        ("P(conversation) from a referral", f["p_conversation_referral"], ""),
        ("Expected referral conversations", "=(B9+B13)*B16*B17", "Formula"),
        ("Total reachable conversations, NYC cardiology", "=B9+B13+B15+B18", "Formula"),
        ("Months of supply at target", "=B19/B2", "Formula: the whole market covers this many months"),
        ("Fresh accounts needed per month at blended rate", "=ROUNDUP(B2/B10,0)", "Formula"),
    ]
    for r in lines:
        ws.append(list(r))
    for row in ws.iter_rows(min_row=2):
        if not str(row[1].value).startswith("="):
            row[1].font = BLUE
    for rr in (6, 7, 8, 10, 12, 14, 16, 17):
        ws.cell(row=rr, column=2).number_format = "0.0%"
    for rr in (9, 13, 15, 18, 19, 20):
        ws.cell(row=rr, column=2).number_format = "0.0"
    _style_sheet(ws, {"A": 46, "B": 12, "C": 52})
    ws.freeze_panes = "A2"
    ws.append([])
    ws.append(["Blue = editable assumption. Black = formula. Change any blue cell and the market math updates."])

    ws = wb.create_sheet("Scoring logic")
    sc = cfg["scoring"]
    ws.append(["Block", "Signal", "Points", "Source", "Why it matters"])
    logic = [
        ("Fit (35)", "Segment: independent cardiology / CHC / small multispecialty / large multispecialty",
         "15 / 11 / 9 / 5", "CMS group size + name", "Owner-run practices decide in one meeting; systems buy centrally"),
        ("Fit (35)", "Cardiologists at the account: 1 / 2-3 / 4-9 / 10-20 / 21+", "5 / 9 / 12 / 10 / 6", "CMS",
         "Enough patient volume to feel the education load, small enough to decide fast"),
        ("Fit (35)", "Sites: 1 / 2 / 3+", "0 / 5 / 8", "CMS addresses", "Consistency across sites is a real pain"),
        ("Need (35)", "Limited-English households at primary ZIP: 30%+ / 20-30 / 12-20 / 6-12 / <6",
         "20 / 16 / 11 / 6 / 2", "Census ACS 2020-24, C16002", "Multilingual education is FlocCare's sharpest edge in NYC"),
        ("Need (35)", "Service line: rhythm / prevention / heart+vascular / general / cardiometabolic",
         "10 / 9 / 8 / 7 / 6", "Practice name", "AFib anticoagulation and prevention are education-heavy"),
        ("Need (35)", "One language group >= 15% of households", "+5", "Census ACS", "Gives the outreach a concrete hook"),
        ("Timing (10)", "Share of cardiologists trained 2010+: >=50% / some / none", "10 / 6 / 3", "CMS grad year",
         "Adoption propensity for digital tools"),
        ("Reach (20)", "Decision-maker: NPPES-named / inferred / unknown", "10 / 6 / 2", "NPPES", "Named > guessed"),
        ("Reach (20)", "Clinical champion: distinct / same person / unknown", "5 / 3 / 0", "CMS",
         "Two threads into a practice beat one"),
        ("Reach (20)", "Direct phone listed", "5", "CMS", "Small practices run on the phone"),
        ("Tiers", f"A >= {cfg['tiers']['A']}, B >= {cfg['tiers']['B']}, else C", "", "",
         "A gets every channel incl. mail; C gets email + ads"),
    ]
    for r in logic:
        ws.append(list(r))
    _style_sheet(ws, {"A": 12, "B": 62, "C": 18, "D": 26, "E": 58}, {"B", "E"})

    ws = wb.create_sheet("Reaction demo")
    ws.append(["Scenario", "Practice", "Day", "Kind", "What happened / what the system did"])
    for d in demo:
        for e in d["timeline"]:
            ws.append([d["title"], d["practice"], e["day"], e["kind"], e["text"]])
    _style_sheet(ws, {"A": 34, "B": 30, "C": 6, "D": 10, "E": 110}, {"E"})

    ws = wb.create_sheet("Sources")
    ws.append(["Source", "What it gives", "Query"])
    for r in [
        ("CMS Doctors & Clinicians (data.cms.gov, mj5m-pzi6)", "Clinicians, specialty, group, size, address, phone",
         "pri_spec = CARDIOVASCULAR DISEASE (CARDIOLOGY); NYC ZIP ranges; pulled 2026-11-23"),
        ("NPPES NPI Registry API", "Organization authorized official (name, title)",
         "enumeration_type=NPI-2; taxonomy Cardiovascular Disease; 5 boroughs; pulled 2026-11-23"),
        ("Census ACS 2020-24 5-year, table C16002 (via Census Reporter)", "Household language + limited English by ZIP",
         "122 NYC ZIPs + 5 counties"),
        ("FlocCare case studies", "Proof for messaging (hypertension/CVD program)",
         "https://www.floccare.ai/hypertension-cvd-case"),
        ("Kessels RPC, J R Soc Med 2003;96:219-222", "Patients forget 40-80% of medical information", "Cited in email 1"),
    ]:
        ws.append(list(r))
    _style_sheet(ws, {"A": 52, "B": 48, "C": 70}, {"A", "B", "C"})

    path = OUT / "FlocCare_NYC_Cardiology_Top75.xlsx"
    wb.save(path)
    return str(path)


def write_demo_md(demo: list[dict], cohort: dict, funnel: dict) -> str:
    lines = ["# Reaction demo: what the system does next", "",
             "Every message below went to the test inbox (`output/outbox/demo/`), never to a clinic.", ""]
    for d in demo:
        lines += [f"## {d['title']}", f"**{d['practice']}** · Tier {d['tier']} · score {d['score']} · "
                  f"final status **{d['final_status']}**", ""]
        if d["sales_ready_reason"]:
            lines += [f"> SALES-READY on Day {d['sales_ready_day']}: {d['sales_ready_reason']}", ""]
        lines += ["| Day | Kind | What happened / decision |", "|---:|---|---|"]
        for e in d["timeline"]:
            lines.append(f"| {e['day']} | {e['kind']} | {e['text'].replace('|', '/')} |")
        lines.append("")
    lines += ["## Cohort run: all 75 with seeded random behavior", "",
              f"Status counts: {cohort['status_counts']}. Sales-ready: {len(cohort['sales_ready'])} of 75 "
              f"({cohort['conversations_rate'] * 100:.0f}%).", "", "## Funnel verdict", "", funnel["verdict"], ""]
    p = OUT / "demo" / "demo_timeline.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p)


def write_csvs(top, all_accounts, messages, cohort, demo):
    pd.DataFrame([top_row(a) for a in top]).to_csv(OUT / "top75_clinics_scored.csv", index=False)
    pd.DataFrame(messages).to_csv(OUT / "top75_messages.csv", index=False)
    pd.DataFrame([{"rank": a.get("rank"), "practice": a["practice"], "id": a["id"], "route": a["route"],
                   "tier": a.get("tier"), "score": a.get("score"), "segment": a["segment"], "zip": a["zip"],
                   "reason": a.get("score_reason") or a.get("exclude_reason")} for a in all_accounts]
                 ).sort_values("rank").to_csv(OUT / "all_accounts_scored.csv", index=False)
    sr = [{"run": "demo", "practice": d["practice"], "day": d["sales_ready_day"], "reason": d["sales_ready_reason"]}
          for d in demo if d["sales_ready_reason"]]
    sr += [{"run": "cohort", "practice": s["practice"], "day": s["day"], "reason": s["reason"]}
           for s in cohort["sales_ready"]]
    pd.DataFrame(sr).to_csv(OUT / "sales_ready.csv", index=False)


def write_dashboard(payload: dict) -> str:
    tpl = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null", json.dumps(payload, default=str).replace("</", "<\\/"))
    p = OUT / "dashboard.html"
    p.write_text(html, encoding="utf-8")
    site = OUT / "site"                     # same page, data beside it (for hosting)
    site.mkdir(exist_ok=True)
    (site / "index.html").write_text(tpl, encoding="utf-8")
    (site / "data.json").write_text(json.dumps(payload, default=str), encoding="utf-8")
    return str(p)


def dashboard_payload(cfg, top, reactive, messages, demo, cohort, funnel, universe, all_accounts) -> dict:
    rules = load_yaml("rules.yaml")
    seq = load_yaml("sequence.yaml")["steps"]
    by_acc: dict[str, list] = {}
    for m in messages:
        by_acc.setdefault(m["account_id"], []).append({k: m[k] for k in ("step", "day", "channel", "to_name",
                                                                         "to_role", "condition", "subject", "body")})
    accts = []
    for a in top:
        r = top_row(a)
        accts.append({"id": a["id"], "rank": a["rank"], "practice": a["practice"], "tier": a["tier"],
                      "score": a["score"], "sub": a["subscores"], "reason": a["score_reason"],
                      "segment": r["Segment"], "borough": a["borough"], "hood": a["neighborhood"],
                      "site": r["Primary site"], "sites": a["n_sites"], "phone": a["phone_display"],
                      "cards": a["n_cardiologists"], "dm": a["dm"]["name"], "dm_title": a["dm"]["title"],
                      "dm_src": r["DM source"], "champ": r["Clinical champion"], "lep": a["lep_pct"],
                      "lang": a["language"], "topic": a["topic"], "msgs": by_acc.get(a["id"], []),
                      "reactive": reactive[a["id"]]})
    seg_counts: dict[str, int] = {}
    for a in all_accounts:
        seg_counts[a["route"]] = seg_counts.get(a["route"], 0) + 1
    return {"generated": cfg["campaign"]["launch_date"], "accounts": accts, "demo": demo, "cohort": cohort,
            "funnel": funnel, "rules": rules, "steps": seq, "routes": seg_counts,
            "universe_listings_manhattan": universe["cardiology_listings_manhattan_only"],
            "test_inbox": cfg["guardrail"]["test_inbox"]}
