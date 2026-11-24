"""Shared helpers: config loading, name/address/phone normalization."""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "data"
OUTPUT = ROOT / "output"


def load_yaml(name: str) -> dict:
    with open(CONFIG / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def settings() -> dict:
    cfg = load_yaml("settings.yaml")
    # Point the guardrail at your own inbox without committing it: export FLOCCARE_TEST_INBOX=you@example.com
    if os.environ.get("FLOCCARE_TEST_INBOX"):
        cfg["guardrail"]["test_inbox"] = os.environ["FLOCCARE_TEST_INBOX"].strip()
    return cfg


# ----------------------------------------------------------------- names
_SUFFIX = re.compile(
    r"[,\.]?\s*\b(P\.?\s?C\.?|P\.?L\.?L\.?C\.?|L\.?L\.?C\.?|L\.?L\.?P\.?|INC\.?|LTD\.?|CORP\.?|"
    r"A PROFESSIONAL CORPORATION|A MEDICAL CORPORATION|PROFESSIONAL CORPORATION)\s*\.?$",
    re.I,
)
_SMALL = {"of", "and", "the", "at", "for", "in", "on"}
_UPPER = {"ny", "nyc", "md", "do", "pc", "ii", "iii", "afib", "pad", "usa", "bx", "dba", "facc", "si"}


def strip_entity_suffix(name: str) -> str:
    s = (name or "").strip().strip(",")
    for _ in range(3):
        s2 = _SUFFIX.sub("", s).strip().strip(",").strip()
        if s2 == s:
            break
        s = s2
    return s


def nice_case(text: str) -> str:
    words = re.split(r"(\s+|-|/)", (text or "").lower())
    out = []
    for i, w in enumerate(words):
        if not w or w.isspace() or w in "-/":
            out.append(w)
            continue
        if w in _UPPER:
            out.append(w.upper())
        elif w in _SMALL and i != 0:
            out.append(w)
        elif re.fullmatch(r"\d+(st|nd|rd|th)", w):
            out.append(w)
        elif w.startswith("mc") and len(w) > 2:
            out.append("Mc" + w[2:].capitalize())
        elif w.startswith("o'") and len(w) > 2:
            out.append("O'" + w[2:].capitalize())
        else:
            out.append(w.capitalize())
    s = "".join(out)
    s = re.sub(r"\bM\.d\b\.?", "M.D.", s)
    s = re.sub(r"\bD\.o\b\.?", "D.O.", s)
    return s


def practice_display(name: str) -> str:
    s = nice_case(strip_entity_suffix(name))
    return re.sub(r"\bM D\b", "MD", s).strip()


def person_display(first: str, last: str) -> str:
    return f"{nice_case(first)} {nice_case(last)}".strip()


def norm_org(name: str) -> str:
    """Normalize an organization name for matching across CMS and NPPES."""
    s = (name or "").upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\b(P C|PC|PLLC|P L L C|LLC|L L C|LLP|INC|LTD|CORP|MD|M D|MDS|DO|D O|PHYSICIAN|PHYSICIANS|THE|DBA)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------- address
_STREET_WORDS = {"STREET": "ST", "AVENUE": "AVE", "ROAD": "RD", "BOULEVARD": "BLVD", "PARKWAY": "PKWY",
                 "PLACE": "PL", "DRIVE": "DR", "EXPRESSWAY": "EXPY", "TURNPIKE": "TPKE"}


def norm_address(line: str) -> str:
    s = (line or "").upper()
    s = re.sub(r"(\d+)\s*-\s*(\d+)", r"\1\2", s)          # Queens hyphenated house numbers
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\b(FL|FLOOR|STE|SUITE|RM|ROOM|APT|UNIT|OFC)\b.*$", "", s)
    s = " ".join(_STREET_WORDS.get(t, t) for t in s.split())
    return s.strip()


def street_name(line: str) -> str:
    """'139 CENTRE ST' -> 'Centre St'; '136 -21 ROOSEVELT AVE' -> 'Roosevelt Ave'."""
    s = re.sub(r"^\s*\d+[A-Z]?(\s*-\s*\d+)?\s+", "", (line or "").upper()).strip()
    s = re.sub(r"\b(FL|FLOOR|STE|SUITE|RM|APT|UNIT)\b.*$", "", s).strip()
    return nice_case(s) if s else nice_case(line)


def street_full(line: str) -> str:
    return nice_case(re.sub(r"\s+", " ", line or "").strip())


# ----------------------------------------------------------------- phone
def phone10(raw: str) -> str:
    d = re.sub(r"\D", "", str(raw or ""))
    if len(d) < 10:
        return ""
    d = d[:10]
    if d[0] in "01":
        return ""
    return d


NYC_AREA_CODES = {"212", "646", "332", "718", "347", "929", "917"}


def is_nyc_phone(p10: str) -> bool:
    return len(p10) == 10 and p10[:3] in NYC_AREA_CODES


def phone_display(p10: str) -> str:
    return f"({p10[:3]}) {p10[3:6]}-{p10[6:]}" if len(p10) == 10 else ""


def borough_for_zip(z: str) -> str:
    p = (z or "")[:3]
    return {"100": "Manhattan", "101": "Manhattan", "102": "Manhattan", "103": "Staten Island",
            "104": "the Bronx", "112": "Brooklyn", "111": "Queens", "113": "Queens", "114": "Queens",
            "116": "Queens"}.get(p, "NYC")
