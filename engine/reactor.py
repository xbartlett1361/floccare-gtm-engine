"""REACT + SURFACE: run the sequence day by day, change course on every signal, flag sales-ready
accounts with the reason why.

The engine is deterministic: same accounts + same events = same decisions. That is what makes
the demo reproducible and the logic auditable.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

from .messages import MessageWriter
from .outbox import Outbox
from .store import Store
from .util import ROOT, load_yaml

REPLY_PATTERNS = [
    ("reply_unsubscribe", r"\b(unsubscribe|remove me|stop emailing|not interested|do not contact|don't contact)\b|^\s*stop\s*$"),
    ("out_of_office", r"out of (the )?office|on vacation|on leave|away until|limited access to email"),
    ("reply_referral", r"(talk|speak|reach out|write|email)\s+(to|with)\s+(our|my|the)\b|handles (this|that|these)|"
                       r"is the (right )?person|looping in|cc'?ing"),
    ("reply_has_materials", r"already (have|use|give|hand out|provide)|we have (our own|handouts|materials)|"
                            r"our own (handouts|materials)"),
    ("reply_not_now", r"not (right )?now|too busy|busy until|next (month|quarter|year)|after the holidays|check back"),
    ("reply_positive", r"\b(yes|sure|interested|send (it|the|me|over)|sounds good|let'?s talk|happy to|call me|"
                       r"book|schedule|15 minutes)\b"),
]


def classify_reply(text: str) -> str:
    """Rule-based intent classifier. In production this is an LLM call with a confidence score;
    anything under threshold goes to a human queue instead of auto-acting."""
    t = text.lower()
    for label, pat in REPLY_PATTERNS:
        if re.search(pat, t):
            return label
    return "reply_unclear"


class Campaign:
    def __init__(self, cfg: dict, accounts: list[dict], run: str, quiet_outbox: bool = False):
        self.cfg = cfg
        self.rules = load_yaml("rules.yaml")
        self.writer = MessageWriter(cfg)
        self.outbox = Outbox(cfg, run_name=run)
        (ROOT / "output").mkdir(exist_ok=True)
        self.store = Store(ROOT / "output" / "floccare_gtm.db", run)
        self.run = run
        self.acc = {a["id"]: a for a in accounts}
        self.state: dict[str, dict] = {}
        for a in accounts:
            self._plan(a)

    # ------------------------------------------------------------------ setup
    def _plan(self, a: dict) -> None:
        steps = [dict(st, status="planned", planned_day=st["day"]) for st in self.writer.planned_steps(a)]
        self.state[a["id"]] = {
            "status": "active", "engagement": 0.0, "steps": steps, "clicked": False, "opens": [],
            "engaged_contacts": set(), "li_connected": False, "email_valid": True, "evidence": [],
            "last_touch_day": None, "signals_since_touch": 0, "log": [], "contacts": self._contacts(a),
            "sales_ready_day": None, "sales_ready_reason": None, "recycle_day": None,
        }
        self.store.upsert_account(a)
        for c in self.state[a["id"]]["contacts"]:
            self.store.contact(a["id"], c["name"], c["role"], c.get("title", ""), "", a["phone"], c["source"])

    def _contacts(self, a: dict) -> list[dict]:
        out = [{"name": a["dm"]["name"], "role": "decision-maker", "title": a["dm"]["title"],
                "source": {"registry": "NPPES authorized official", "inferred": a["dm"].get("inferred_how", "inferred"),
                           "unknown": "to enrich"}[a["dm"]["source"]]}]
        if a["champion"]:
            out.append({"name": f"Dr. {a['champion']['name']}", "role": "clinical champion", "title": "Cardiologist",
                        "source": "CMS: " + a["champion"]["why"]})
        if a.get("entry_contact"):
            out.append({"name": a["entry_contact"]["name"], "role": "front office", "title": a["entry_contact"]["title"],
                        "source": "NPPES authorized official"})
        return out

    # ------------------------------------------------------------------ logging
    def _log(self, aid: str, day: int, kind: str, text: str) -> None:
        self.state[aid]["log"].append({"day": day, "kind": kind, "text": text})
        self.store.decision(aid, day, kind, text)

    # ------------------------------------------------------------------ delivery
    def _send(self, aid: str, day: int, step_id: str, channel: str, template: str, audience: str = "dm",
              scheduled: bool = True, **extra) -> None:
        a = self.acc[aid]
        subj, body = self.writer.render(a, template, **extra)
        to = self.writer.recipient(a, audience)
        if extra.get("to_name"):
            to = {"name": extra["to_name"], "role": extra.get("to_role", "contact")}
        if channel == "email":
            path = self.outbox.deliver(intended_name=to["name"], intended_email=None, subject=subj, body=body,
                                       account_id=aid, step=step_id, day=day)
            self.store.touch(aid, day, step_id, channel, to["name"], subj, "delivered_to_test_inbox",
                             self.outbox.test_inbox, str(path.relative_to(ROOT)))
            self._log(aid, day, "touch", f"EMAIL '{subj}' to {to['name']} ({to['role']}) -> test inbox")
        else:
            self.outbox.task(account_id=aid, step=step_id, day=day, channel=channel, to_name=to["name"],
                             subject=subj, body=body)
            self.store.touch(aid, day, step_id, channel, to["name"], subj, "task_created")
            verb = {"phone": "CALL TASK", "linkedin": "LINKEDIN DRAFT", "direct_mail": "MAIL PACKET (Lob)",
                    "ads": "AD AUDIENCE SYNC"}.get(channel, channel.upper())
            self._log(aid, day, "touch", f"{verb}: {subj} -> {to['name']}")
        if scheduled:   # replies we send in reaction don't reset the silence clock
            st = self.state[aid]
            st["last_touch_day"] = day
            st["signals_since_touch"] = 0

    # ------------------------------------------------------------------ the loop
    def run_days(self, day_from: int, day_to: int, events: dict[int, list[tuple]] | None = None) -> None:
        events = events or {}
        for day in range(day_from, day_to + 1):
            for aid in self.acc:                  # scheduled touches go out first thing...
                self._execute_due(aid, day)
            for ev in events.get(day, []):        # ...prospects react during the day
                self.apply_event(day, *ev)
            for aid, st in self.state.items():
                if st["status"] == "active" and all(s["status"] != "planned" for s in st["steps"]) \
                        and st["steps"] and day >= max(s["day"] for s in st["steps"]):
                    st["status"] = "nurture"
                    st["recycle_day"] = day + self.cfg["funnel"]["recycle_after_days"]
                    self._log(aid, day, "decision", f"Sequence finished with no reply. Moved to nurture "
                              f"(monthly free template, retargeting ads). Re-enters on Day {st['recycle_day']} "
                              f"or sooner on a trigger (new site, new clinician, job post).")
        self.store.commit()

    def _execute_due(self, aid: str, day: int) -> None:
        st = self.state[aid]
        if st["status"] not in ("active",):
            return
        for s in st["steps"]:
            if s["status"] != "planned" or s["day"] > day:
                continue
            if s.get("skip_if") == "clicked" and st["clicked"]:
                s["status"] = "skipped"
                self._log(aid, day, "decision", f"Skipped {s['id']}: they already clicked, a bump would be noise.")
                continue
            if s.get("requires") == "linkedin_connected" and not st["li_connected"]:
                s["status"] = "skipped"
                self._log(aid, day, "decision", f"Skipped {s['id']}: LinkedIn request not accepted, no message.")
                continue
            if s["channel"] == "email" and not st["email_valid"]:
                s["status"] = "skipped"
                self._log(aid, day, "decision", f"Skipped {s['id']}: email bounced; phone and mail carry the sequence.")
                continue
            if st["last_touch_day"] is not None and st["last_touch_day"] < day and st["signals_since_touch"] == 0 \
                    and s["day"] >= 2:
                self._log(aid, day, "decision", f"Silence since Day {st['last_touch_day']}. Next touch switches to "
                          f"{s['channel'].replace('_', ' ')} ({s['id']}).")
            self._send(aid, day, s["id"], s["channel"], s["template"], s["audience"])
            s["status"] = "sent"
            s["sent_day"] = day

    # ------------------------------------------------------------------ events
    def apply_event(self, day: int, aid: str, etype: str, contact: str | None = None, payload: dict | None = None):
        payload = payload or {}
        st = self.state[aid]
        if etype == "reply":
            text = payload.get("text", "")
            etype = classify_reply(text)
            self._log(aid, day, "event", f"REPLY from {contact or 'decision-maker'}: \"{text}\" -> classified {etype}")
        else:
            self._log(aid, day, "event", f"{etype.upper().replace('_', ' ')}"
                      f"{' by ' + contact if contact else ''}{' ' + json.dumps(payload) if payload else ''}")
        if st["status"] in ("suppressed",):
            self._log(aid, day, "decision", "Account is suppressed. Event recorded, no action.")
            return
        pts = self.rules["engagement_points"].get(etype, 0)
        st["engagement"] += pts
        if pts:
            st.setdefault("ledger", []).append(etype)
        if st["status"] == "sales_ready":
            self.store.event(aid, day, etype, contact or "", payload, st["engagement"])
            self._log(aid, day, "decision", "Account is already with the AE: activity forwarded to them, automation stays off.")
            return
        if etype not in ("bounce", "out_of_office", "reply_unsubscribe"):
            st["signals_since_touch"] += 1
        if etype == "email_open":
            st["opens"].append(day)
        if etype in ("link_click", "qr_scan", "reply_positive", "reply_referral", "reply_has_materials",
                     "linkedin_reply", "call_interested", "pricing_page_visit"):
            st["engaged_contacts"].add(contact or "decision-maker")
            st["evidence"].append(f"{etype.replace('_', ' ')} (Day {day}, {contact or 'decision-maker'})")
        if etype == "link_click":
            st["clicked"] = True
        self.store.event(aid, day, etype, contact or "", payload, st["engagement"])

        for r in self.rules["reactions"].get(etype, []):
            if r.get("when") == "hot_opens":
                w = self.rules["hot_opens"]
                if sum(1 for d in st["opens"] if d > day - w["window_days"]) < w["count"]:
                    continue
            self._log(aid, day, "decision", r["why"])
            for action in r["do"]:
                self._act(aid, day, action, contact, payload)
        self._check_sales_ready(aid, day, etype)

    def _act(self, aid: str, day: int, action: str, contact: str | None, payload: dict) -> None:
        st = self.state[aid]
        name, _, arg = action.partition(":")
        planned = [s for s in st["steps"] if s["status"] == "planned"]
        if name == "send":
            to = {}
            if contact and contact != "decision-maker":
                to = {"to_name": contact, "to_role": "engaged contact"}
            if arg == "referral_intro":
                ref = payload.get("referred_name", "Office manager")
                to = {"to_name": ref, "to_role": "referred contact"}
                self._send(aid, day, arg, "email", arg, scheduled=False, ref_first=ref.split(" ")[0], **to)
            elif arg == "not_now_ack":
                self._send(aid, day, arg, "email", arg, scheduled=False,
                           snooze_month=payload.get("snooze_month", "two months"), **to)
            else:
                self._send(aid, day, arg, "email", arg, scheduled=False, **to)
        elif name == "task" and arg == "call_next_business_day":
            phone_soon = [s for s in planned if s["channel"] == "phone" and s["day"] <= day + 1]
            if phone_soon:
                self._log(aid, day, "action", f"Call already queued for Day {phone_soon[0]['day']}; kept it.")
            else:
                st["steps"].append({"id": "call_hot", "day": day + 1, "channel": "phone", "template": "call_1",
                                    "audience": "practice", "status": "planned", "planned_day": day + 1,
                                    "tiers": ["A", "B", "C"]})
                self._log(aid, day, "action", f"Added a human call for Day {day + 1}.")
        elif name == "task" and arg == "reply_personally":
            self._log(aid, day, "action", "Task: reply personally on LinkedIn today.")
        elif name == "pull_forward_call":
            nxt = next((s for s in sorted(planned, key=lambda s: s["day"]) if s["channel"] == "phone"), None)
            if nxt and nxt["day"] > day + 1:
                self._log(aid, day, "action", f"Pulled {nxt['id']} forward from Day {nxt['day']} to Day {day + 1}.")
                nxt["day"] = day + 1
            elif not nxt:
                self._act(aid, day, "task:call_next_business_day", contact, payload)
            else:
                self._log(aid, day, "action", f"{nxt['id']} is already due Day {nxt['day']}.")
        elif name == "skip":
            for s in planned:
                if s["id"] == arg:
                    s["status"] = "skipped"
                    self._log(aid, day, "action", f"Cancelled {arg}.")
        elif name == "unlock":
            st["li_connected"] = True
            self._log(aid, day, "action", "LinkedIn message step unlocked.")
        elif name == "stop_sequence":
            for s in planned:
                s["status"] = "cancelled"
            self._log(aid, day, "action", f"Stopped automation ({len(planned)} remaining steps cancelled).")
        elif name == "mark_sales_ready":
            self._sales_ready(aid, day, f"explicit interest ({payload.get('text', 'live call')})")
        elif name == "draft":
            pass  # the AE handoff draft is written inside _sales_ready
        elif name == "add_contact":
            nm = payload.get("referred_name") or payload.get("name") or contact or "new contact"
            st["contacts"].append({"name": nm, "role": payload.get("role", "referred contact"), "source": "reply/call"})
            self.store.contact(aid, nm, payload.get("role", "referred contact"), source="captured from reply/call")
            self._log(aid, day, "action", f"Added contact {nm} ({payload.get('role', 'referred')}).")
        elif name == "pause":
            n = int(arg)
            for s in planned:
                s["day"] += n
            self._log(aid, day, "action", f"Paused {n} days: remaining steps shifted (next now Day "
                      f"{min((s['day'] for s in planned), default='-')}).")
        elif name == "snooze":
            for s in planned:
                s["status"] = "cancelled"
            st["status"] = "snoozed"
            st["recycle_day"] = day + int(arg)
            self._log(aid, day, "action", f"Snoozed. Re-enters with a fresh angle on Day {st['recycle_day']}.")
        elif name == "suppress":
            st["status"] = "suppressed"
            self._log(aid, day, "action", "Suppressed on every channel (email, phone, mail, LinkedIn, ads).")
        elif name == "shift_schedule":
            ret = int(payload.get("return_day", day + 7))
            delta = ret + 1 - day
            for s in planned:
                s["day"] += delta
            self._log(aid, day, "action", f"Out of office until Day {ret}: shifted {len(planned)} steps by {delta} days.")
        elif name == "mark_email_invalid":
            st["email_valid"] = False
            self._log(aid, day, "action", "Email marked invalid; contact queued for re-enrichment.")
        elif name == "notify_ae_if_ready":
            pass

    # ------------------------------------------------------------------ surface
    def _check_sales_ready(self, aid: str, day: int, etype: str) -> None:
        st, a = self.state[aid], self.acc[aid]
        if st["status"] in ("sales_ready", "suppressed", "snoozed"):
            return
        sr = self.rules["sales_ready"]
        if st["engagement"] >= sr["engagement_threshold"] and a.get("tier") in sr["eligible_tiers"]:
            from collections import Counter
            parts = ", ".join(f"{n}x {k.replace('_', ' ')}" if n > 1 else k.replace("_", " ")
                              for k, n in Counter(st.get("ledger", [])).items())
            self._sales_ready(aid, day, f"engagement {st['engagement']:.0f} >= {sr['engagement_threshold']} on a "
                              f"Tier {a['tier']} account ({parts})")
        elif len(st["engaged_contacts"]) >= sr["multi_thread_contacts"]:
            self._sales_ready(aid, day, f"{len(st['engaged_contacts'])} people engaged: "
                              f"{', '.join(sorted(st['engaged_contacts']))}")

    def _sales_ready(self, aid: str, day: int, trigger: str) -> None:
        st, a = self.state[aid], self.acc[aid]
        if st["status"] == "sales_ready":
            return
        for s in st["steps"]:
            if s["status"] == "planned":
                s["status"] = "cancelled"
        st["status"] = "sales_ready"
        st["sales_ready_day"] = day
        ev = "; ".join(st["evidence"][-4:]) or "see timeline"
        reason = f"{trigger}. Evidence: {ev}. Fit: Tier {a['tier']} ({a['score']}/100): {a['score_reason']}"
        st["sales_ready_reason"] = reason
        subj, body = self.writer.render(a, "ae_handoff", reason=f"{trigger}; {ev}")
        alert = f"[#gtm-sales-ready] Day {day}: {a['practice']} ({a['neighborhood']})\nWHY: {reason}\n\n{body}"
        self.store.alert(aid, day, alert)
        path = ROOT / "output" / "alerts" / self.run
        path.mkdir(parents=True, exist_ok=True)
        (path / f"{aid}_day{day:02d}.md").write_text(f"# {subj}\n\n{alert}\n", encoding="utf-8")
        self._log(aid, day, "surface", f"SALES-READY -> AE alerted. Reason: {trigger}.")

    # ------------------------------------------------------------------ results
    def finalize(self) -> None:
        for aid, a in self.acc.items():
            st = self.state[aid]
            self.store.upsert_account(a, st)
        self.store.commit()

    def summary(self) -> dict:
        c = defaultdict(int)
        for st in self.state.values():
            c[st["status"]] += 1
        return dict(c)
