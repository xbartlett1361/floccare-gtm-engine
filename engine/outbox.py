"""GUARDRAIL: every outbound message lands in a test inbox or a draft folder. Never a real clinic.

Three layers:
  1. The prospect's address is never put in To/Cc/Bcc. It goes in X-Intended-Recipient for review.
  2. _enforce() inspects the built message and raises if any recipient isn't the test inbox.
  3. Network delivery (smtp_sandbox) only runs against an allowlisted sandbox host (e.g. Mailtrap),
     and still only to the test inbox. Default mode writes .eml files and sends nothing.
"""
from __future__ import annotations

import json
import os
import re
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, getaddresses
from pathlib import Path

from .util import ROOT


class GuardrailViolation(RuntimeError):
    pass


class Outbox:
    def __init__(self, cfg: dict, run_name: str = "launch"):
        g = cfg["guardrail"]
        self.mode = g["mode"]
        self.test_inbox = g["test_inbox"].lower()
        self.prefix = g["subject_prefix"]
        self.sender = cfg["campaign"]["sender"]
        self.dir = ROOT / g["outbox_dir"] / run_name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.dir / "tasks.jsonl"
        self.smtp_host = os.environ.get("SMTP_HOST", "")
        if self.mode == "smtp_sandbox" and self.smtp_host not in g["smtp_host_allowlist"]:
            raise GuardrailViolation(f"SMTP host '{self.smtp_host}' is not an allowlisted sandbox. Refusing to start.")
        if self.mode not in ("local_outbox", "smtp_sandbox", "gmail_drafts"):
            raise GuardrailViolation(f"Unknown delivery mode {self.mode}")
        self.count = 0

    # ---------------------------------------------------------------- email
    def build(self, *, intended_name: str, intended_email: str | None, subject: str, body: str,
              account_id: str, step: str, day: int) -> EmailMessage:
        m = EmailMessage()
        m["From"] = f"{self.sender['name']} <gtm-sandbox@floccare.ai>"
        m["To"] = self.test_inbox                      # always, no exceptions
        m["Subject"] = self.prefix + subject
        m["Date"] = formatdate(localtime=True)
        m["X-Intended-Recipient"] = f"{intended_name} <{intended_email or 'pending-enrichment'}>"
        m["X-FlocCare-Account"] = account_id
        m["X-FlocCare-Step"] = step
        m["X-FlocCare-Day"] = str(day)
        m.set_content(body)
        return m

    def _enforce(self, m: EmailMessage) -> None:
        addrs = [a.lower() for _, a in getaddresses(m.get_all("To", []) + m.get_all("Cc", []) +
                                                    m.get_all("Bcc", []))]
        if not addrs or any(a != self.test_inbox for a in addrs):
            raise GuardrailViolation(f"Blocked: recipients {addrs} are not the test inbox")

    def deliver(self, **kw) -> Path:
        m = self.build(**kw)
        self._enforce(m)
        day = int(kw["day"])
        folder = self.dir / f"day_{day:+03d}"
        folder.mkdir(exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_-]", "", f"{kw['account_id']}_{kw['step']}")
        path = folder / f"{safe}.eml"
        path.write_bytes(bytes(m))
        if self.mode == "smtp_sandbox":
            with smtplib.SMTP(self.smtp_host, int(os.environ.get("SMTP_PORT", "2525"))) as s:
                if os.environ.get("SMTP_USER"):
                    s.starttls()
                    s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
                self._enforce(m)
                s.send_message(m, to_addrs=[self.test_inbox])
        elif self.mode == "gmail_drafts":
            self._gmail_draft(m)
        self.count += 1
        return path

    def _gmail_draft(self, m: EmailMessage) -> None:
        """Creates a Gmail *draft* addressed to the test inbox. Needs google-api-python-client and a
        token.json from the Gmail API quickstart; drafts are never sent by this code."""
        import base64
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_file(str(ROOT / "token.json"),
                                                      ["https://www.googleapis.com/auth/gmail.compose"])
        raw = base64.urlsafe_b64encode(bytes(m)).decode()
        build("gmail", "v1", credentials=creds).users().drafts().create(
            userId="me", body={"message": {"raw": raw}}).execute()

    # --------------------------------------------------------- other channels
    def task(self, *, account_id: str, step: str, day: int, channel: str, to_name: str, subject: str,
             body: str) -> None:
        """Phone, LinkedIn, direct mail and ad-audience steps become tasks for a human or an API
        (Lob for mail, LinkedIn Matched Audiences for ads). Nothing is executed automatically."""
        with open(self.tasks_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"account_id": account_id, "step": step, "day": day, "channel": channel,
                                "to": to_name, "title": subject, "body": body}) + "\n")
