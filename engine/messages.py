"""ENGAGE: write every message in the sequence for an account, plus the reactive replies.

Personalization comes from sourced fields only (practice, people, street, ZIP language data,
service line). If a fact isn't in the data, the template doesn't claim it.
"""
from __future__ import annotations

from jinja2 import Environment, StrictUndefined

from .util import load_yaml

SAMPLE_FILES = {"general": "home-blood-pressure.md", "rhythm": "afib-blood-thinner.md",
                "heart_vascular": "pad-walking-plan.md", "prevention": "heart-numbers.md",
                "cardiometabolic": "diabetes-and-heart.md"}

KESSELS = ("Research suggests patients forget 40 to 80% of what they hear in a visit almost immediately "
           "(Kessels, J R Soc Med, 2003), so the take-home sheet does a lot of the work.")


class MessageWriter:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        seq = load_yaml("sequence.yaml")
        self.steps = seq["steps"]
        self.templates = seq["templates"]
        self.env = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)

    # ------------------------------------------------------------ context
    def context(self, a: dict, **extra) -> dict:
        c = self.cfg["campaign"]
        dm, ch = a["dm"], a["champion"]
        if dm["source"] == "unknown":
            greet, dm_ref = "Hello,", "the doctors"
        elif dm["is_physician"]:
            greet, dm_ref = f"Dr. {dm['last']},", f"Dr. {dm['last']}"
        else:
            greet, dm_ref = f"Hi {dm['first']},", dm["name"]
        lang = a["language"]
        langs = lang.split(" and ") if lang else []
        lang_phrase = (", ".join(langs) + " and English") if langs else ""
        street = a["primary"].get("street") or "your"
        lep, ne = a["lep_pct"] or 0, a["non_english_pct"] or 0
        if lang and lep >= 20:
            hook = (f"About {lep:.0f}% of households near your {street} office have limited English, and many "
                    f"speak {lang} at home (Census ACS 2020-24). When the take-home instructions are only in "
                    f"English, a lot of what's said in the visit gets lost.")
        elif lang:
            hook = (f"Around {ne:.0f}% of households near your {street} office speak a language other than "
                    f"English at home, many of them {lang} (Census ACS 2020-24). {KESSELS}")
        else:
            hook = KESSELS
        slug = a["id"][-6:].lower()
        base = f"{c['links']['sample_base']}/{SAMPLE_FILES[a['focus']]}"
        s = c["sender"]
        ctx = {
            "practice": a["practice_2p"], "practice_3p": a["practice_3p"], "practice_label": a["practice"],
            "practice_mail": "" if a["practice"].startswith("Dr. ") else a["practice"],
            "dm_mail": (f"Dr. {dm['name']}" if dm["is_physician"] else dm["name"]),
            "for_patients": a["for_patients"],
            "greet": greet, "greet_short": greet, "dm_ref": dm_ref, "dm_name": dm["name"], "dm_title": dm["title"],
            "has_champion": bool(ch), "champ_name": ch["name"] if ch else "",
            "champ_greet": f"Dr. {ch['last']}," if ch else greet,
            "li_first": (ch or dm)["first"] or "there",
            "hook": hook, "language": lang, "lang_phrase": lang_phrase,
            "in_lang": f" in {lang_phrase}" if lang else "",
            "in_their_lang": " in their own language" if lang else "",
            "subject_lang": ("/".join(langs) + " + English ") if langs else "",
            "subject_lang_suffix": f", in {lang}" if lang else "",
            "lang_or_plain": f"{lang} " if lang else "",
            "topic": a["topic"], "topic_short": a["topic_short"], "topic_patients": a["topic_patients"],
            "street": street, "street_full": a["primary"].get("street_full", ""), "zip": a["zip"],
            "borough": a["borough"], "neighborhood": a["neighborhood"],
            "phone": (a["phone_display"] + (f" ({a['phone_note']})" if a.get("phone_note") else ""))
                     if a["phone_display"] else "(no listed number: route to research)",
            "n_sites": a["n_sites"], "n_cardiologists": a["n_cardiologists"],
            "sites_phrase": f"your {a['n_sites']} offices" if a["n_sites"] > 1 else "your office",
            "link_email1": f"{base}?ref={slug}-e1", "link_champion": f"{base}?ref={slug}-ch",
            "link_bump": f"{base}?ref={slug}-e2", "link_qr": f"{base}?ref={slug}-qr",
            "link_referral": f"{base}?ref={slug}-ref",
            "case_link": c["links"]["case_study"], "calendar": c["links"]["calendar"],
            "sender_name": s["name"], "sender_phone": s["phone"],
            "sender_block": (f"{s['name']}\n{s['title']} · {s['signature_url']} · {s['phone']}\n"
                             f"{s['postal_footer']} · Reply \"stop\" and I won't email again."),
            "wave": 1, "tier": a.get("tier", ""), "score": a.get("score", ""),
            "reason": a.get("score_reason", ""), "snooze_month": "", "ref_first": "",
        }
        ctx.update(extra)
        return ctx

    def render(self, a: dict, template_id: str, **extra) -> tuple[str, str]:
        t = self.templates[template_id]
        ctx = self.context(a, **extra)
        subj = self.env.from_string(t["subject"]).render(ctx).strip()
        body = self.env.from_string(t["body"]).render(ctx).strip()
        return subj, body

    # ------------------------------------------------------------ sequence
    def planned_steps(self, a: dict) -> list[dict]:
        out = []
        for st in self.steps:
            if a.get("tier") not in st["tiers"]:
                continue
            if st.get("requires") == "distinct_champion" and not a["champion"]:
                continue
            out.append(st)
        return out

    def recipient(self, a: dict, audience: str) -> dict:
        dm, ch = a["dm"], a["champion"]
        if audience == "champion" and ch:
            return {"name": f"Dr. {ch['name']}", "role": "clinical champion"}
        if audience == "champion_or_dm":
            p = ch or dm
            return {"name": p["name"], "role": "clinical champion" if ch else "decision-maker"}
        if audience == "practice":
            return {"name": f"Front desk {a['phone_display']}", "role": "practice line"}
        if audience == "account":
            return {"name": a["practice"], "role": "ad audience"}
        return {"name": dm["name"], "role": f"decision-maker ({dm['title']})"}

    def write_sequence(self, a: dict) -> list[dict]:
        msgs = []
        for st in self.planned_steps(a):
            subj, body = self.render(a, st["template"])
            to = self.recipient(a, st["audience"])
            msgs.append({"account_id": a["id"], "practice": a["practice"], "step": st["id"], "day": st["day"],
                         "channel": st["channel"], "to_name": to["name"], "to_role": to["role"],
                         "condition": st.get("requires") or (f"skip if {st['skip_if']}" if st.get("skip_if") else ""),
                         "subject": subj, "body": body})
        return msgs

    def write_reactive(self, a: dict) -> dict:
        out = {}
        for tid, extra in [("on_click", {}), ("on_qr", {}), ("objection_has_materials", {}),
                           ("referral_intro", {"ref_first": "Maria"}), ("not_now_ack", {"snooze_month": "February"}),
                           ("ae_handoff", {"reason": "positive reply to the sample email"})]:
            subj, body = self.render(a, tid, **extra)
            out[tid] = {"subject": subj, "body": body}
        return out
