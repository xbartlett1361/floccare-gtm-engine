"""TRACK: one SQLite file holds accounts, contacts, every touch, every event and every alert,
so any number in the report can be traced back to a row."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, run TEXT, practice TEXT, segment TEXT, route TEXT,
  tier TEXT, score INTEGER, rank INTEGER, status TEXT, engagement REAL, sales_ready INTEGER,
  sales_ready_day INTEGER, sales_ready_reason TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, run TEXT, account_id TEXT,
  name TEXT, role TEXT, title TEXT, email TEXT, phone TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS touches (id INTEGER PRIMARY KEY AUTOINCREMENT, run TEXT, account_id TEXT, day INTEGER,
  step TEXT, channel TEXT, to_name TEXT, subject TEXT, status TEXT, delivered_to TEXT, file TEXT);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, run TEXT, account_id TEXT, day INTEGER,
  type TEXT, contact TEXT, payload TEXT, engagement_after REAL);
CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, run TEXT, account_id TEXT, day INTEGER,
  kind TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, run TEXT, account_id TEXT, day INTEGER,
  text TEXT);
"""


class Store:
    def __init__(self, path: Path, run: str):
        self.run = run
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA secure_delete = ON")   # re-runs overwrite old rows instead of leaving them in free pages
        self.db.executescript(SCHEMA)
        for t in ("accounts", "contacts", "touches", "events", "decisions", "alerts"):
            self.db.execute(f"DELETE FROM {t} WHERE run = ?", (run,))
        self.db.commit()

    def upsert_account(self, a: dict, st: dict | None = None) -> None:
        st = st or {}
        slim = {k: v for k, v in a.items() if k not in ("clinicians",)}
        self.db.execute("INSERT OR REPLACE INTO accounts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            a["id"], self.run, a["practice"], a["segment"], a["route"], a.get("tier"), a.get("score"),
            a.get("rank"), st.get("status", "planned"), st.get("engagement", 0), int(st.get("status") == "sales_ready"),
            st.get("sales_ready_day"), st.get("sales_ready_reason"), json.dumps(slim, default=str)))

    def contact(self, account_id: str, name: str, role: str, title: str = "", email: str = "", phone: str = "",
                source: str = "") -> None:
        self.db.execute("INSERT INTO contacts (run, account_id, name, role, title, email, phone, source) "
                        "VALUES (?,?,?,?,?,?,?,?)", (self.run, account_id, name, role, title, email, phone, source))

    def touch(self, account_id, day, step, channel, to_name, subject, status, delivered_to="", file=""):
        self.db.execute("INSERT INTO touches (run, account_id, day, step, channel, to_name, subject, status, "
                        "delivered_to, file) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (self.run, account_id, day, step, channel, to_name, subject, status, delivered_to, file))

    def event(self, account_id, day, etype, contact, payload, engagement_after):
        self.db.execute("INSERT INTO events (run, account_id, day, type, contact, payload, engagement_after) "
                        "VALUES (?,?,?,?,?,?,?)", (self.run, account_id, day, etype, contact,
                                                   json.dumps(payload), engagement_after))

    def decision(self, account_id, day, kind, text):
        self.db.execute("INSERT INTO decisions (run, account_id, day, kind, text) VALUES (?,?,?,?,?)",
                        (self.run, account_id, day, kind, text))

    def alert(self, account_id, day, text):
        self.db.execute("INSERT INTO alerts (run, account_id, day, text) VALUES (?,?,?,?)",
                        (self.run, account_id, day, text))

    def commit(self):
        self.db.commit()
