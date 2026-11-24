"""ENRICH: turn raw clinician rows into accounts with a decision-maker, a clinical champion,
sites, segment, service line and neighborhood language context.

Account = one practice (CMS group PAC ID, or a self-employed cardiologist). A practice with
three offices is one account with three sites, so the owner is never emailed three times.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from collections import Counter

import pandas as pd

from .util import (CONFIG, borough_for_zip, is_nyc_phone, norm_address, norm_org, nice_case, person_display,
                   phone10, phone_display, practice_display, street_full, street_name)

# Centralized buying: these go to an enterprise motion, not the clinic sequence.
EXTRA_SYSTEM_ORGS = {"4688563018": "MEMORIAL SLOAN KETTERING (MEMORIAL CARDIOPULMONARY GROUP)",
                     "4082883673": "NEWYORK-PRESBYTERIAN QUEENS"}
HOSPITAL_CAMPUS = {"630 W 168TH ST", "161 FORT WASHINGTON AVE", "177 FORT WASHINGTON AVE", "425 E 61ST ST",
                   "1275 YORK AVE", "160 E 53RD ST", "1 PARK AVE", "8900 VAN WYCK EXPY"}

DIAGNOSTIC = re.compile(r"IMAGING|RADIOLOG|ULTRASOUND|MAMMOGRAPH|NUCLEAR|\bSPECT\b|TESTING|LABORATORY|DIAGNOSTIC")
PEDIATRIC = re.compile(r"PEDIATRIC")
NO_SITE = re.compile(r"TELECARE|HOUSE CALL|MOBILE MEDICAL")
CHC = re.compile(r"HEALTH CENTER|COMMUNITY HEALTH|HEALTH PLAN|COMMUNITY DEVELOPMENT|HUMAN SERVICES|"
                 r"HEALTH AND HOUSING|HEALTH NETWORK|FAMILY HEALTH CENTER")
CARDIO_NAME = re.compile(r"CARDI|HEART|VASCULAR|RHYTHM|ARRHYTHM")

TOPICS = {
    "rhythm": ("Living with AFib: your blood thinner, explained", "AFib blood-thinner", "AFib"),
    "prevention": ("Your heart numbers: blood pressure, cholesterol and blood sugar", "heart-numbers", "prevention"),
    "heart_vascular": ("Leg pain when you walk: what PAD is and your walking plan", "PAD walking-plan", "PAD"),
    "general": ("Checking your blood pressure at home", "home blood-pressure", "hypertension"),
    "cardiometabolic": ("Diabetes and your heart: five things to do this month", "diabetes-and-heart",
                        "cardiometabolic"),
}

OWNER_T = re.compile(r"OWNER|PRESIDENT|CEO|C\. ?E\. ?O|PRINCIPAL|MANAGING MEMBER|MEMBER|PARTNER|DIRECTOR|"
                     r"FOUNDER|SOLE|PROPRIET|^M\.?D\.?$|DOCTOR|PHYSICIAN|CARDIOLOGIST|PLLC|OFFICER|DR\.")
OPS_T = re.compile(r"MANAGER|ADMINISTRAT|\bCOO\b|\bCFO\b|OPERATIONS|TREASURER|SECRETARY|MANAGEMENT|BUSINESS")
LOW_T = re.compile(r"BILL|CREDENTIAL|COMPLIANCE|SERVICE REP|PROVIDER|ENROLLMENT|ASSISTANT|^AM$")


def title_role(title: str) -> str:
    t = (title or "").upper().strip()
    if not t or LOW_T.search(t):
        return "low"
    if OPS_T.search(t):
        return "operations"
    if OWNER_T.search(t):
        return "owner"
    return "low"


def _acc_id(key: str) -> str:
    return "NYC-CARD-" + hashlib.sha1(key.encode()).hexdigest()[:6].upper()


def load_zip_context() -> dict:
    df = pd.read_csv(CONFIG / "nyc_zip_context.csv", dtype=str).fillna("")
    return {r.zip: r._asdict() for r in df.itertuples(index=False)}


def language_context(zip5: str, acs: pd.DataFrame, zctx: dict) -> dict:
    row = acs[acs["geo"] == zip5]
    out = {"lep_pct": None, "non_english_pct": None, "language": "", "language_family": "",
           "language_share_pct": None, "language_hook": False}
    if row.empty:
        return out
    r = row.iloc[0]
    hh = float(r["households"]) or 1.0
    lep = (r["spanish_lep"] + r["indo_euro_lep"] + r["asian_pi_lep"] + r["other_lep"]) / hh
    fams = {"spanish": r["spanish"] / hh, "indo_euro": r["indo_euro"] / hh,
            "asian_pi": r["asian_pi"] / hh, "other": r["other"] / hh}
    ranked = sorted(fams.items(), key=lambda kv: kv[1], reverse=True)
    fam, share = ranked[0]
    c = zctx.get(zip5, {})
    names = {"spanish": "Spanish", "asian_pi": c.get("api_label") or "Chinese",
             "indo_euro": c.get("ie_label", ""), "other": c.get("other_label", "")}
    label = names[fam]
    fam2, share2 = ranked[1]
    if label and share2 >= 0.15 and names[fam2]:      # e.g. Sunset Park: Spanish and Chinese
        langs = label.split(" and ")
        second = names[fam2].split(" and ")[0]
        if second not in langs:
            langs.append(second)
        label = langs[0] if len(langs) == 1 else ", ".join(langs[:-1]) + " and " + langs[-1]
    out.update(lep_pct=round(lep * 100, 1), non_english_pct=round((1 - r["english_only"] / hh) * 100, 1),
               language=label if share >= 0.15 and label else "", language_family=fam,
               language_share_pct=round(share * 100, 1), language_hook=bool(share >= 0.15 and label))
    return out


class NppesIndex:
    def __init__(self, nppes: pd.DataFrame):
        self.df = nppes.copy()
        self.df["norm"] = self.df["organization_name"].map(norm_org)
        self.by_norm: dict[str, list[dict]] = {}
        for rec in self.df.to_dict("records"):
            self.by_norm.setdefault(rec["norm"], []).append(rec)
        self.names = list(self.by_norm)

    def match_org(self, raw_name: str) -> dict | None:
        n = norm_org(raw_name)
        if not n:
            return None
        recs = self.by_norm.get(n)
        if not recs:
            best = difflib.get_close_matches(n, self.names, n=1, cutoff=0.88)
            recs = self.by_norm.get(best[0]) if best else None
        if not recs:
            return None
        recs = sorted(recs, key=lambda r: {"owner": 0, "operations": 1, "low": 2}[title_role(r["ao_title"])])
        return recs[0]

    def match_person(self, first: str, last: str, city: str = "") -> dict | None:
        f, l = first.upper().split(" ")[0], last.upper()
        hits = self.df[(self.df["ao_first"].str.upper().str.split(" ").str[0] == f) &
                       (self.df["ao_last"].str.upper() == l)]
        if hits.empty:
            return None
        hits = hits[~hits["organization_name"].str.upper().str.contains(DIAGNOSTIC)]
        if hits.empty:
            return None
        hits = hits.assign(c=hits["organization_name"].str.upper().str.contains(CARDIO_NAME),
                           here=hits["query_city"].str.upper() == city.upper())
        best = hits.sort_values(["here", "c"], ascending=False).iloc[0].to_dict()
        best["same_city"] = bool(best["here"])
        return best


def _sites(rows: pd.DataFrame) -> list[dict]:
    sites: dict[tuple, dict] = {}
    for r in rows.itertuples(index=False):
        if not r.adr_ln_1:
            continue
        key = (norm_address(r.adr_ln_1), r.zip5)
        s = sites.setdefault(key, {"addr_key": key[0], "zip": r.zip5, "street_full": street_full(r.adr_ln_1),
                                   "street": street_name(r.adr_ln_1), "city": nice_case(r.city), "phones": Counter(),
                                   "rows": 0, "apt": False})
        s["rows"] += 1
        p = phone10(r.phone_raw)
        if p:
            s["phones"][p] += 1
        if re.search(r"\bAPT\b", f"{r.adr_ln_1} {r.adr_ln_2}".upper()):
            s["apt"] = True
    out = []
    for s in sites.values():
        ranked = sorted(s["phones"].items(), key=lambda kv: (is_nyc_phone(kv[0]), kv[1]), reverse=True)
        s["phone"] = ranked[0][0] if ranked else ""
        del s["phones"]
        out.append(s)
    out.sort(key=lambda s: (is_nyc_phone(s["phone"]), bool(s["phone"]), not s["apt"], s["rows"]), reverse=True)
    return out


def _clinicians(rows: pd.DataFrame) -> list[dict]:
    seen = {}
    for r in rows.itertuples(index=False):
        k = (r.first.upper(), r.last.upper())
        if k not in seen:
            gy = int(r.grd_yr) if str(r.grd_yr).isdigit() else None
            seen[k] = {"first": r.first, "last": r.last, "name": person_display(r.first, r.last),
                       "cred": r.cred or "MD", "grd_yr": gy}
    return list(seen.values())


def _segment(raw: str, org_id: str, members: int, n_card: int, system_ids: set) -> tuple[str, str, str]:
    """Return (segment, route, exclude_reason)."""
    up = raw.upper()
    if org_id in system_ids:
        return "health_system", "enterprise", "centralized buying: route to enterprise AE"
    if PEDIATRIC.search(up):
        return "excluded", "excluded", "pediatric cardiology: different audience and materials"
    if NO_SITE.search(up):
        return "excluded", "excluded", "telehealth/house-call entity: no outpatient site"
    if DIAGNOSTIC.search(up) and "TREATMENT" not in up:
        return "excluded", "excluded", "diagnostic/imaging only: no ongoing patient-education relationship"
    if CHC.search(up):
        return "community_health_center", "outreach", ""
    if not org_id:
        return "independent_cardiology", "outreach", ""
    if members >= 100:
        return "large_multispecialty", "outreach", ""
    if CARDIO_NAME.search(up) or (members and n_card / members >= 0.5 and members <= 10):
        return "independent_cardiology", "outreach", ""
    return "independent_multispecialty", "outreach", ""


def _focus(raw: str, segment: str) -> str:
    up = raw.upper()
    if re.search(r"RHYTHM|ARRHYTHM|ELECTROPHYS", up):
        return "rhythm"
    if re.search(r"PREVENT|WELLNESS", up):
        return "prevention"
    if re.search(r"VASCULAR|VEIN", up):
        return "heart_vascular"
    if segment == "independent_cardiology":
        return "general"
    return "cardiometabolic"


def _is_physician(first: str, last: str, title: str, raw_org: str, clinicians: list[dict]) -> bool:
    fl = (first.upper().split(" ")[0], last.upper())
    if any((c["first"].upper().split(" ")[0], c["last"].upper()) == fl for c in clinicians):
        return True
    if re.search(r"\bM\.?D\b|DOCTOR|PHYSICIAN|CARDIOLOGIST|\bDR\b", (title or "").upper()):
        return True
    return bool(re.search(rf"{re.escape(last.upper())}.{{0,25}}(M\.?\s?D|D\.?O\.?|PHYSICIAN)", raw_org.upper()))


def build_accounts(cms: pd.DataFrame, nppes: pd.DataFrame, acs: pd.DataFrame, universe: dict) -> list[dict]:
    zctx = load_zip_context()
    idx = NppesIndex(nppes)
    system_ids = {k for k in universe["health_system_groups"] if k[0].isdigit()} | set(EXTRA_SYSTEM_ORGS)
    nyc = cms[cms["zip5"].str[:3].isin(["100", "101", "102", "103", "104", "111", "112", "113", "114", "116"])]

    accounts: list[dict] = []
    org_site_people: set[tuple] = set()   # (person, addr_key, zip) already covered by a group

    # ---- group practices
    for org_id, rows in nyc[nyc["org_pac_id"] != ""].groupby("org_pac_id"):
        raw = rows["facility_name"].iloc[0]
        members = int(rows["num_org_mem"].iloc[0] or 0)
        clin = _clinicians(rows)
        sites = _sites(rows)
        for r in rows.itertuples(index=False):
            org_site_people.add((r.first.upper(), r.last.upper(), norm_address(r.adr_ln_1), r.zip5))
        seg, route, why = _segment(raw, org_id, members, len(clin), system_ids)
        if sites and sites[0]["addr_key"] in HOSPITAL_CAMPUS and route == "outreach":
            seg, route, why = "health_system", "enterprise", "practice sits on a hospital campus"
        accounts.append(_finish(_acc_id(org_id), org_id, raw, members, clin, sites, seg, route, why,
                                idx, acs, zctx, solo=False))

    # ---- self-employed cardiologists (blank group): one account per person, minus group-covered sites
    solo = nyc[nyc["org_pac_id"] == ""]
    for (f, l), rows in solo.groupby([solo["first"].str.upper(), solo["last"].str.upper()]):
        keep = rows[[(f, l, norm_address(a), z) not in org_site_people
                     for a, z in zip(rows["adr_ln_1"], rows["zip5"])]]
        if keep.empty:
            continue
        clin = _clinicians(keep)
        sites = _sites(keep)
        if not sites:
            continue
        p = idx.match_person(clin[0]["first"], clin[0]["last"], _nppes_city(sites[0]))
        raw = p["organization_name"] if p and p["same_city"] else f"Dr. {clin[0]['name']} (cardiology practice)"
        seg, route, why = "independent_cardiology", "outreach", ""
        if all(s["addr_key"] in HOSPITAL_CAMPUS for s in sites):
            seg, route, why = "health_system", "enterprise", "clinician practices on a hospital campus"
        elif p and DIAGNOSTIC.search(raw.upper()):
            raw = f"Dr. {clin[0]['name']} (cardiology practice)"
        acc = _finish(_acc_id(f"SOLO-{f}-{l}"), "", raw, 1, clin, sites, seg, route, why, idx, acs, zctx,
                      solo=True, solo_registry=p)
        accounts.append(acc)
    return accounts


def _nppes_city(site: dict) -> str:
    b = borough_for_zip(site["zip"])
    return {"Manhattan": "NEW YORK", "Brooklyn": "BROOKLYN", "the Bronx": "BRONX",
            "Staten Island": "STATEN ISLAND"}.get(b, (site.get("city") or "").upper())


def _finish(acc_id, org_id, raw, members, clin, sites, seg, route, why, idx, acs, zctx, solo, solo_registry=None):
    primary = sites[0] if sites else {"zip": "", "street": "", "street_full": "", "phone": "", "city": ""}
    lang = language_context(primary["zip"], acs, zctx)
    focus = _focus(raw, seg)
    topic, topic_short, topic_patients = TOPICS[focus]
    if raw.startswith("Dr. "):
        last = nice_case(clin[0]["last"])
        display, practice_2p, practice_3p = f"Dr. {clin[0]['name']} (solo cardiology)", "your practice", f"Dr. {last}'s practice"
        for_patients = f"Dr. {last}'s patients"
    else:
        display = practice_display(raw)
        practice_2p = practice_3p = display
        for_patients = f"{display} patients"
        # Legal entities named after people ("Shahed Ahmed, M.D.", "Traube Marush and Plawes MD") read
        # badly mid-sentence, so prose uses the doctor's name instead; tables keep the legal name.
        named = [c for c in clin if re.search(rf"\b{re.escape(c['last'].upper())}\b", raw.upper())]
        if named or re.search(r"\bM\.?\s?D\b|PHYSICIAN", raw.upper()):
            last = nice_case(named[0]["last"]) if named else ""
            practice_2p = "your practice"
            practice_3p = f"Dr. {last}'s practice" if last else "the practice"
            for_patients = f"Dr. {last}'s patients" if last else "your patients"

    # ---- decision-maker
    dm = {"name": "", "first": "", "last": "", "title": "", "role": "", "source": "unknown",
          "is_physician": False, "npi": ""}
    entry_contact = None
    rec = solo_registry if solo else idx.match_org(raw)
    if rec:
        role = title_role(rec["ao_title"])
        if role in ("owner", "operations"):
            dm.update(name=person_display(rec["ao_first"], rec["ao_last"]), first=nice_case(rec["ao_first"]),
                      last=nice_case(rec["ao_last"]), title=nice_case(rec["ao_title"]), role=role,
                      source="registry", npi=rec["npi"])
            # Owner of a cardiology practice is treated as a physician (greeted "Dr."); first call verifies.
            dm["is_physician"] = role == "owner" and (seg == "independent_cardiology" or _is_physician(
                rec["ao_first"], rec["ao_last"], rec["ao_title"], raw, clin))
        else:
            entry_contact = {"name": person_display(rec["ao_first"], rec["ao_last"]),
                             "title": nice_case(rec["ao_title"]), "source": "NPPES authorized official"}
    if dm["source"] == "unknown" and clin:
        named = [c for c in clin if re.search(rf"\b{re.escape(c['last'].upper())}\b", raw.upper())]
        pick, how = None, ""
        if solo:
            pick, how = clin[0], "self-employed cardiologist (CMS)"
        elif named:
            pick, how = named[0], "name on the practice entity"
        elif seg == "independent_cardiology" and members and members <= 10:
            dated = [c for c in clin if c["grd_yr"]]
            pick = min(dated, key=lambda c: c["grd_yr"]) if dated else clin[0]
            how = "most senior cardiologist in a small group"
        if pick:
            dm.update(name=pick["name"], first=nice_case(pick["first"].split(" ")[0]), last=nice_case(pick["last"]),
                      title="Physician owner (inferred)" if how != "most senior cardiologist in a small group"
                      else "Senior partner (inferred)", role="owner", source="inferred", is_physician=True,
                      inferred_how=how)
    if dm["source"] == "unknown":
        dm.update(name="Practice Administrator (to enrich)", title="Practice Administrator", role="operations")

    # ---- clinical champion: most recently trained cardiologist who is not the decision-maker
    dm_key = (dm["first"].upper(), dm["last"].upper())
    cands = [c for c in clin if (c["first"].upper().split(" ")[0], c["last"].upper()) != dm_key]
    champion, champ_status = None, "unknown"
    if cands:
        c = max(cands, key=lambda c: c["grd_yr"] or 0)
        champion = {"name": c["name"], "first": nice_case(c["first"].split(" ")[0]), "last": nice_case(c["last"]),
                    "cred": c["cred"], "grd_yr": c["grd_yr"], "is_physician": True,
                    "why": "most recently trained cardiologist at the practice"}
        champ_status = "named_distinct"
    elif dm["is_physician"]:
        champ_status = "same_as_dm"

    dated = [c["grd_yr"] for c in clin if c["grd_yr"]]
    recent_share = sum(1 for g in dated if g >= 2010) / len(dated) if dated else 0.0
    phone = primary.get("phone", "")
    phone_note = "" if not phone or is_nyc_phone(phone) else "out-of-area number on file (likely billing): verify"

    return {
        "id": acc_id, "org_pac_id": org_id, "raw_name": raw, "practice": display, "practice_2p": practice_2p,
        "practice_3p": practice_3p, "for_patients": for_patients, "segment": seg, "route": route,
        "exclude_reason": why, "focus": focus, "topic": topic, "topic_short": topic_short,
        "topic_patients": topic_patients, "num_org_mem": members, "clinicians": clin,
        "n_cardiologists": len(clin), "sites": sites, "n_sites": len(sites), "primary": primary,
        "zip": primary["zip"], "borough": borough_for_zip(primary["zip"]),
        "neighborhood": zctx.get(primary["zip"], {}).get("neighborhood", primary.get("city", "")),
        **lang, "dm": dm, "entry_contact": entry_contact, "champion": champion, "champion_status": champ_status,
        "phone": phone, "phone_display": phone_display(phone), "phone_note": phone_note,
        "phone_is_local": is_nyc_phone(phone), "recent_share": round(recent_share, 2),
        "email_status": "needs enrichment (Apollo / Hunter / Crustdata person-contact API)",
    }


def dedupe_people(accounts: list[dict]) -> None:
    """One person, one sequence. Walk accounts best-first; a decision-maker already claimed by a
    higher-ranked account links this account to it; a claimed champion is dropped."""
    claimed: dict[str, str] = {}
    ranked = sorted([a for a in accounts if a["route"] == "outreach"], key=lambda a: a["rank"])
    for a in ranked:
        dm = a["dm"]
        key = f"{dm['first']} {dm['last']}".upper().strip()
        if dm["source"] != "unknown" and key in claimed:
            a.update(route="linked", segment=a["segment"],
                     exclude_reason=f"same decision-maker as {claimed[key]} (worked in that sequence)")
            continue
        if dm["source"] != "unknown":
            claimed[key] = a["practice"]
        ch = a["champion"]
        if ch:
            ck = f"{ch['first']} {ch['last']}".upper()
            if ck in claimed:
                a["champion"] = None
                a["champion_status"] = "same_as_dm" if dm["is_physician"] else "unknown"
            else:
                claimed[ck] = a["practice"]
