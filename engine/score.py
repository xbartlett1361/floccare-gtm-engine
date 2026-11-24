"""PRIORITIZE: 100-point score = Fit (35) + Need (35) + Timing (10) + Reach (20).

Every point is traceable to a sourced field, and every account carries a one-line reason.
"""
from __future__ import annotations


def _band(value: int, bands: dict) -> int:
    for k, pts in bands.items():
        if k.endswith("+"):
            if value >= int(k[:-1]):
                return pts
        elif "-" in k:
            lo, hi = map(int, k.split("-"))
            if lo <= value <= hi:
                return pts
        elif value == int(k):
            return pts
    return 0


def _threshold(value: float, table: list) -> int:
    for floor, pts in table:
        if value >= floor:
            return pts
    return table[-1][1]


def score_account(a: dict, cfg: dict) -> dict:
    s = cfg["scoring"]
    if a["route"] != "outreach":
        a.update(score=None, tier="-", subscores={}, score_reason=a["exclude_reason"])
        a.pop("rank", None)
        return a

    fit_seg = s["fit"]["segment"].get(a["segment"], 0)
    fit_size = _band(max(a["n_cardiologists"], 1), s["fit"]["cardiologists"])
    fit_sites = _band(min(a["n_sites"], 3), {"1": 0, "2": s["fit"]["sites"]["2"], "3": s["fit"]["sites"]["3+"]})
    fit = fit_seg + fit_size + fit_sites

    lep = a["lep_pct"] or 0.0
    need_lang = _threshold(lep, s["need"]["lep_households_pct"])
    need_line = s["need"]["service_line"][a["focus"]]
    need_hook = s["need"]["language_hook_bonus"] if a["language_hook"] else 0
    need = need_lang + need_line + need_hook

    timing = _threshold(a["recent_share"], s["timing"]["recent_trained_share"])

    reach_dm = s["reach"]["decision_maker"][{"registry": "registry_named", "inferred": "inferred"}.get(
        a["dm"]["source"], "unknown")]
    reach_ch = s["reach"]["champion"][a["champion_status"]]
    reach_ph = s["reach"]["direct_phone"] if a.get("phone_is_local") else 0
    reach = reach_dm + reach_ch + reach_ph

    total = fit + need + timing + reach
    tiers = cfg["tiers"]
    tier = "A" if total >= tiers["A"] else "B" if total >= tiers["B"] else "C"

    bits = []
    bits.append({"independent_cardiology": "independent cardiology practice",
                 "community_health_center": "community health center",
                 "independent_multispecialty": "independent multispecialty group",
                 "large_multispecialty": "large multispecialty group"}[a["segment"]])
    bits.append(f"{a['n_cardiologists']} cardiologist(s), {a['n_sites']} site(s)")
    if a["language_hook"]:
        bits.append(f"{a['lep_pct']:.0f}% limited-English households in {a['zip']}, mostly {a['language']}")
    else:
        bits.append(f"{lep:.0f}% limited-English households in {a['zip']}")
    bits.append({"registry": f"decision-maker named in NPPES ({a['dm']['title']})",
                 "inferred": "decision-maker inferred", "unknown": "decision-maker to enrich"}[a["dm"]["source"]])
    if a["champion_status"] == "named_distinct":
        bits.append(f"champion: Dr. {a['champion']['last']}")

    a.update(score=total, tier=tier,
             subscores={"fit": fit, "need": need, "timing": timing, "reach": reach,
                        "fit_segment": fit_seg, "fit_size": fit_size, "fit_sites": fit_sites,
                        "need_language": need_lang, "need_service_line": need_line, "need_hook": need_hook,
                        "reach_dm": reach_dm, "reach_champion": reach_ch, "reach_phone": reach_ph},
             score_reason="; ".join(bits))
    return a


def score_all(accounts: list[dict], cfg: dict) -> list[dict]:
    for a in accounts:
        score_account(a, cfg)
    ranked = sorted([a for a in accounts if a["score"] is not None],
                    key=lambda a: (a["score"], a["subscores"]["need"], a["n_cardiologists"]), reverse=True)
    for i, a in enumerate(ranked, 1):
        a["rank"] = i
    return accounts
