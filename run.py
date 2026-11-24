#!/usr/bin/env python3
"""FlocCare GTM engine: one command, end to end.

    python run.py            # cached public-data pulls (works offline)
    python run.py --live     # re-pull CMS, NPPES and Census live
    python run.py --top 75   # size of the monthly cohort worked up in full

Stages: source -> enrich -> score -> engage (write every message) -> launch (Days -7..2 into the
test inbox) -> react (scripted demo + 75-account cohort) -> surface (sales-ready alerts) -> report.
Nothing is ever sent to a real prospect: see engine/outbox.py and tests/test_guardrail.py.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys

from engine import enrich, funnel, report, score, simulate, sources
from engine.messages import MessageWriter
from engine.reactor import Campaign
from engine.util import OUTPUT, settings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="re-pull public data instead of the cached files")
    ap.add_argument("--top", type=int, default=None)
    ap.add_argument("--no-dashboard", action="store_true")
    args = ap.parse_args()
    cfg = settings()
    n = args.top or cfg["campaign"]["monthly_cohort_size"]

    for sub in ("outbox", "alerts", "demo"):
        shutil.rmtree(OUTPUT / sub, ignore_errors=True)
    OUTPUT.mkdir(exist_ok=True)

    print("1/7 SOURCE   CMS clinicians, NPPES officials, Census language data", "(live)" if args.live else "(cached)")
    universe = sources.load_universe_counts()
    if args.live:
        system = [k for k in universe["health_system_groups"] if k[0].isdigit()]
        cms = sources.fetch_cms_live(cfg, system)
        nppes = sources.fetch_nppes_live(cfg, ["NEW YORK", "BROOKLYN", "BRONX", "STATEN ISLAND", "FLUSHING",
                                               "FOREST HILLS", "JAMAICA", "ASTORIA", "ELMHURST"])
        acs = sources.fetch_acs_live(sorted(set(cms["zip5"])))
    else:
        cms, nppes, acs = sources.load_cms_cached(), sources.load_nppes_cached(), sources.load_acs_cached()
    print(f"           {len(cms)} clinician-site rows, {len(nppes)} registry officials, {len(acs)} ZIP/county rows")

    print("2/7 ENRICH   accounts, sites, decision-makers, champions, language context")
    accounts = enrich.build_accounts(cms, nppes, acs, universe)
    print("3/7 SCORE    fit + need + timing + reach, then one-person-one-sequence dedupe")
    score.score_all(accounts, cfg)
    enrich.dedupe_people(accounts)
    score.score_all(accounts, cfg)
    ranked = sorted([a for a in accounts if a["route"] == "outreach"], key=lambda a: a["rank"])
    top = ranked[:n]
    routes = {}
    for a in accounts:
        routes[a["route"]] = routes.get(a["route"], 0) + 1
    print(f"           {len(accounts)} accounts {routes}; top {n}: "
          f"A={sum(a['tier'] == 'A' for a in top)} B={sum(a['tier'] == 'B' for a in top)} "
          f"C={sum(a['tier'] == 'C' for a in top)}")

    print("4/7 ENGAGE   writing the full sequence + reactive replies for each account")
    writer = MessageWriter(cfg)
    messages = [m for a in top for m in writer.write_sequence(a)]
    reactive = {a["id"]: writer.write_reactive(a) for a in top}
    print(f"           {len(messages)} sequence messages written")

    print("5/7 LAUNCH   Days -7..2 for the cohort -> test inbox + task queue")
    launch = Campaign(cfg, top, run="launch")
    launch.run_days(-7, 2)
    launch.finalize()
    print(f"           {launch.outbox.count} emails delivered to {cfg['guardrail']['test_inbox']} (local .eml)")

    print("6/7 REACT    scripted demo (8 behaviors) + seeded cohort run (75 accounts, 25 days)")
    _, demo = simulate.run_demo(cfg, top)
    _, cohort = simulate.run_cohort(cfg, top)
    for d in demo:
        print(f"           {d['title'][:58]:<58} -> {d['final_status']}")
    print(f"           cohort: {cohort['status_counts']}")

    print("7/7 REPORT   workbook, CSVs, demo timeline, dashboard")
    fm = funnel.model(cfg, accounts, universe)
    report.write_csvs(top, accounts, messages, cohort, demo)
    xlsx = report.write_workbook(top, accounts, messages, fm, demo, cfg)
    md = report.write_demo_md(demo, cohort, fm)
    (OUTPUT / "funnel.json").write_text(json.dumps(fm, indent=2), encoding="utf-8")
    if not args.no_dashboard:
        dash = report.write_dashboard(report.dashboard_payload(cfg, top, reactive, messages, demo, cohort, fm,
                                                               universe, accounts))
        print(f"           {dash}")
    print(f"           {xlsx}\n           {md}")
    print("\nFUNNEL: " + fm["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
