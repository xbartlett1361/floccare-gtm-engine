"""Run: python -m pytest -q   (or: python tests/test_guardrail.py)

Proves the one hard rule: nothing reaches a real prospect.
"""
import copy
import os
import sys
from email import message_from_bytes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.outbox import GuardrailViolation, Outbox  # noqa: E402
from engine.reactor import classify_reply  # noqa: E402
from engine.util import settings  # noqa: E402

CFG = settings()
TEST = CFG["guardrail"]["test_inbox"].lower()


def test_real_address_never_reaches_to_header():
    ob = Outbox(CFG, run_name="_test")
    path = ob.deliver(intended_name="Dr. Real Person", intended_email="real.doctor@realclinic.com",
                      subject="hello", body="x", account_id="T1", step="email_1", day=1)
    msg = message_from_bytes(path.read_bytes())
    assert msg["To"].lower() == TEST
    assert "realclinic.com" in msg["X-Intended-Recipient"]
    assert msg["Subject"].startswith(CFG["guardrail"]["subject_prefix"])


def test_enforce_blocks_any_other_recipient():
    ob = Outbox(CFG, run_name="_test")
    m = ob.build(intended_name="x", intended_email=None, subject="s", body="b", account_id="T", step="s", day=1)
    m.replace_header("To", "someone@clinic.com")
    try:
        ob._enforce(m)
        raise AssertionError("guardrail did not fire")
    except GuardrailViolation:
        pass
    m2 = ob.build(intended_name="x", intended_email=None, subject="s", body="b", account_id="T", step="s", day=1)
    m2["Bcc"] = "hidden@clinic.com"
    try:
        ob._enforce(m2)
        raise AssertionError("guardrail did not catch Bcc")
    except GuardrailViolation:
        pass


def test_smtp_refuses_non_sandbox_host():
    cfg = copy.deepcopy(CFG)
    cfg["guardrail"]["mode"] = "smtp_sandbox"
    os.environ["SMTP_HOST"] = "smtp.gmail.com"
    try:
        Outbox(cfg, run_name="_test")
        raise AssertionError("should refuse a real SMTP host")
    except GuardrailViolation:
        pass
    finally:
        os.environ.pop("SMTP_HOST", None)


def test_every_generated_email_went_to_test_inbox():
    emls = list((ROOT / "output" / "outbox").rglob("*.eml"))
    assert emls, "run `python run.py` first"
    for p in emls:
        msg = message_from_bytes(p.read_bytes())
        assert msg["To"].lower() == TEST, p
        assert not msg.get("Cc") and not msg.get("Bcc"), p


def test_reply_classifier():
    assert classify_reply("Please remove me from your list.") == "reply_unsubscribe"
    assert classify_reply("Not interested, thanks") == "reply_unsubscribe"
    assert classify_reply("I am out of the office until Monday") == "out_of_office"
    assert classify_reply("Please speak with our office manager, she handles this") == "reply_referral"
    assert classify_reply("We already give patients handouts") == "reply_has_materials"
    assert classify_reply("Too busy right now, check back after the holidays") == "reply_not_now"
    assert classify_reply("Sure, send it over") == "reply_positive"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
