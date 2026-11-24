"""Funnel math: can NYC cardiology produce 75 new first conversations a month? Shows the work."""
from __future__ import annotations

import math


def model(cfg: dict, accounts: list[dict], universe: dict) -> dict:
    f = cfg["funnel"]
    target = f["target_first_conversations_per_month"]
    out = [a for a in accounts if a["route"] == "outreach"]
    tiers = {t: sum(1 for a in out if a["tier"] == t) for t in ("A", "B", "C")}
    p = f["p_conversation_by_tier"]
    exp_pass1 = {t: round(tiers[t] * p[t], 1) for t in tiers}
    pass1 = sum(tiers[t] * p[t] for t in tiers)
    blended = pass1 / max(len(out), 1)

    # Practice sites: CMS counts distinct cardiology addresses; subtract the independent sites we hold.
    total_sites = sum(universe["distinct_practice_sites_adrs_id"].values())
    indep_sites = len({(s["addr_key"], s["zip"]) for a in out for s in a["sites"]})
    system_sites = max(total_sites - indep_sites, 0)
    sys_conv = round(system_sites * f["p_conversation_health_system_site"], 1)

    recycle = round(sum(tiers[t] * (1 - p[t]) * p[t] * f["recycle_multiplier"] for t in tiers), 1)
    referrals = round((pass1 + sys_conv) * f["referral_rate_per_conversation"] * f["p_conversation_referral"], 1)
    total_year = round(pass1 + sys_conv + recycle + referrals, 1)

    accounts_needed = math.ceil(target / blended) if blended else None
    return {
        "target_per_month": target,
        "independent_accounts": len(out), "tiers": tiers, "p_by_tier": p, "expected_pass1_by_tier": exp_pass1,
        "expected_pass1": round(pass1, 1), "blended_rate": round(blended, 3),
        "cms_cardiology_sites_total": total_sites, "independent_sites": indep_sites,
        "health_system_sites": system_sites, "expected_health_system": sys_conv,
        "expected_recycle_pass": recycle, "expected_referrals": referrals,
        "total_reachable_conversations": total_year,
        "months_of_supply_at_target": round(total_year / target, 1),
        "accounts_needed_per_month_at_blended_rate": accounts_needed,
        "verdict": (f"Working every independent NYC cardiology practice once yields about {pass1:.0f} first "
                    f"conversations; adding hospital-system sites, a 90-day recycle and referrals brings the whole "
                    f"market to about {total_year:.0f}. That is {total_year / target:.1f} months of a 75/month target. "
                    f"Hitting 75 every month needs about {accounts_needed} fresh accounts a month at the blended "
                    f"rate, so the same engine has to widen: cardiometabolic-adjacent specialties in NYC "
                    f"(endocrinology, nephrology), then metro cardiology (Long Island, Westchester, North Jersey)."),
    }
