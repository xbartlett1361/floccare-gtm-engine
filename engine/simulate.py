"""Demo + cohort simulation.

demo:   eight scripted prospects, one per behavior (click, hot opens, silence, objection, referral,
        not-now, out-of-office/bounce, unsubscribe). Shows exactly what the system does next.
cohort: all 75 accounts with seeded random behavior drawn from the funnel assumptions, to check
        that the funnel math holds when the engine actually runs.
"""
from __future__ import annotations

import random

from .reactor import Campaign

SCENARIOS = [
    {"key": "click_then_call", "pick": 5, "title": "Clicks the sample, then takes the call",
     "events": [(1, "email_open", "dm"), (2, "link_click", "dm"), (3, "call_interested", "practice manager")]},
    {"key": "hot_opens_then_qr", "pick": 0, "title": "Opens three times, never clicks, then scans the mailed QR",
     "events": [(-3, "linkedin_accept", "champion"), (1, "email_open", "dm"), (1, "email_open", "dm"),
                (1, "email_open", "dm"),
                (2, "call_gatekeeper", "front desk", {"name": "Maria Lopez", "role": "office manager"}),
                (9, "qr_scan", "Maria Lopez"), (10, "link_click", "Maria Lopez")]},
    {"key": "silence", "pick": 9, "title": "Total silence: channel escalation, then nurture", "events": []},
    {"key": "objection_then_yes", "pick": 1, "title": "Objects ('we already have handouts'), then says yes",
     "events": [(2, "reply", "dm", {"text": "Thanks, but we already give patients the AHA handouts."}),
                (14, "reply", "dm", {"text": "Ok, send it over and let's find 15 minutes next week."})]},
    {"key": "referral", "pick": 14, "title": "Refers us to the office manager, who engages",
     "events": [(1, "reply", "dm", {"text": "Please speak with our office manager Elena Ruiz, she handles this.",
                                    "referred_name": "Elena Ruiz", "role": "office manager"}),
                (2, "link_click", "Elena Ruiz")]},
    {"key": "not_now", "pick": 18, "title": "'Not now, check back after the holidays'",
     "events": [(2, "reply", "dm", {"text": "Too busy right now. Check back after the holidays.",
                                    "snooze_month": "February"})]},
    {"key": "ooo_and_bounce", "pick": 24, "title": "Auto-reply out of office, then the champion's email bounces",
     "events": [(1, "reply", "dm", {"text": "I am out of the office until December 10 with limited access to email.",
                                    "return_day": 9}),
                (11, "bounce", "champion"), (16, "qr_scan", "dm"), (17, "link_click", "dm")]},
    {"key": "unsubscribe", "pick": 32, "title": "Asks to be removed",
     "events": [(1, "reply", "dm", {"text": "Please remove me from your list."})]},
]


def _who(a: dict, token: str) -> str:
    if token == "dm":
        return a["dm"]["name"]
    if token == "champion":
        return f"Dr. {a['champion']['name']}" if a["champion"] else a["dm"]["name"]
    return token


def run_demo(cfg: dict, top: list[dict]) -> tuple[Campaign, list[dict]]:
    chosen = []
    used = set()
    for sc in SCENARIOS:
        i = sc["pick"]
        while top[i]["id"] in used or top[i]["dm"]["source"] == "unknown" or not top[i].get("phone_is_local"):
            i += 1
        used.add(top[i]["id"])
        chosen.append((sc, top[i]))
    camp = Campaign(cfg, [a for _, a in chosen], run="demo")
    events: dict[int, list[tuple]] = {}
    for sc, a in chosen:
        for ev in sc["events"]:
            day, etype, who = ev[0], ev[1], ev[2]
            payload = ev[3] if len(ev) > 3 else None
            events.setdefault(day, []).append((a["id"], etype, _who(a, who), payload))
    camp.run_days(-7, 25, events)
    camp.finalize()
    out = []
    for sc, a in chosen:
        st = camp.state[a["id"]]
        out.append({"key": sc["key"], "title": sc["title"], "account_id": a["id"], "practice": a["practice"],
                    "tier": a["tier"], "score": a["score"], "final_status": st["status"],
                    "engagement": st["engagement"], "sales_ready_day": st["sales_ready_day"],
                    "sales_ready_reason": st["sales_ready_reason"], "recycle_day": st["recycle_day"],
                    "timeline": st["log"]})
    return camp, out


# Behavior assumptions for the cohort run (per account, over one sequence). Opens are inflated by
# Apple Mail Privacy Protection, which is why they carry almost no weight in the engine.
COHORT_P = {
    "A": {"open": 0.60, "click": 0.16, "reply": 0.12, "qr": 0.12, "gatekeeper": 0.35, "call_interested": 0.06,
          "li_accept": 0.30, "bounce": 0.08},
    "B": {"open": 0.55, "click": 0.09, "reply": 0.08, "qr": 0.0, "gatekeeper": 0.25, "call_interested": 0.03,
          "li_accept": 0.25, "bounce": 0.08},
    "C": {"open": 0.50, "click": 0.05, "reply": 0.04, "qr": 0.0, "gatekeeper": 0.0, "call_interested": 0.0,
          "li_accept": 0.0, "bounce": 0.08},
}
REPLY_MIX = [("Yes, send it over. Happy to talk.", 0.30),
             ("Please speak with our office manager, she handles this.", 0.15),
             ("We already have our own handouts.", 0.15),
             ("Too busy right now, check back after the holidays.", 0.25),
             ("Please remove me from your list.", 0.10),
             ("I am out of the office until next week.", 0.05)]


def run_cohort(cfg: dict, top: list[dict], seed: int = 7) -> tuple[Campaign, dict]:
    rng = random.Random(seed)
    camp = Campaign(cfg, top, run="cohort")
    events: dict[int, list[tuple]] = {}
    for a in top:
        p = COHORT_P[a["tier"]]
        dm = a["dm"]["name"]
        add = lambda d, *e: events.setdefault(d, []).append((a["id"], *e))
        if rng.random() < p["li_accept"]:
            add(rng.choice([-4, -3, -2]), "linkedin_accept", dm)
        if rng.random() < p["bounce"]:
            add(1, "bounce", dm)
        if rng.random() < p["open"]:
            for _ in range(rng.choice([1, 1, 2, 3])):
                add(rng.choice([1, 1, 2, 5]), "email_open", dm)
        if rng.random() < p["click"]:
            add(rng.choice([1, 2, 5, 6, 12]), "link_click", rng.choice([dm, "champion"]))
        if rng.random() < p["gatekeeper"]:
            add(3, "call_gatekeeper", "front desk", {"name": "Office manager", "role": "office manager"})
        if rng.random() < p["qr"]:
            add(rng.choice([9, 10, 11]), "qr_scan", dm)
        if rng.random() < p["call_interested"]:
            add(rng.choice([3, 15]), "call_interested", "practice manager")
        if rng.random() < p["reply"]:
            r, acc = rng.random(), 0.0
            for text, w in REPLY_MIX:
                acc += w
                if r <= acc:
                    pl = {"text": text}
                    if "office manager" in text:
                        pl.update(referred_name="Office manager", role="office manager")
                    if "out of the office" in text:
                        pl["return_day"] = 8
                    add(rng.choice([1, 2, 3, 6, 13]), "reply", dm, pl)
                    break
    camp.run_days(-7, 25, events)
    camp.finalize()
    summ = camp.summary()
    sr = [{"account_id": aid, "practice": camp.acc[aid]["practice"], "tier": camp.acc[aid]["tier"],
           "day": st["sales_ready_day"], "reason": st["sales_ready_reason"]}
          for aid, st in camp.state.items() if st["status"] == "sales_ready"]
    return camp, {"status_counts": summ, "sales_ready": sorted(sr, key=lambda x: x["day"]),
                  "conversations_rate": round(len(sr) / len(top), 3), "seed": seed}
