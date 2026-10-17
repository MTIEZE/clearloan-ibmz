"""SQLite storage. One connection per request, closed at the end of the request."""
import json
import sqlite3
from datetime import datetime, timezone

from flask import g

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('applicant', 'staff')),
  display_name  TEXT NOT NULL,
  totp_secret   TEXT,
  created_at    TEXT NOT NULL
);

-- Keyed by email (even unknown ones) so the answer never reveals whether an account exists.
CREATE TABLE IF NOT EXISTS login_attempts (
  email        TEXT PRIMARY KEY,
  failures     INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT
);

CREATE TABLE IF NOT EXISTS applications (
  id              TEXT PRIMARY KEY,
  token           TEXT NOT NULL UNIQUE,
  user_id         INTEGER NOT NULL REFERENCES users(id),
  created_at      TEXT NOT NULL,
  identity_enc    BLOB NOT NULL,          -- Fernet-encrypted JSON, only the gateway can read it
  identity_masked TEXT NOT NULL,          -- JSON
  first_name      TEXT NOT NULL,
  audit_sex       TEXT NOT NULL,          -- fairness audit only, never sent to a model
  age_band        TEXT NOT NULL,
  financial       TEXT NOT NULL,          -- JSON, what the risk model receives
  language        TEXT NOT NULL,
  model_used      TEXT NOT NULL,
  decision        TEXT NOT NULL,
  risk_score      INTEGER NOT NULL,
  reasons         TEXT NOT NULL,          -- JSON
  llm             TEXT NOT NULL,          -- JSON, with the token (name is put back on read)
  prompt          TEXT NOT NULL,
  pii_found       INTEGER NOT NULL,
  latency_ms      INTEGER NOT NULL,
  final_decision  TEXT NOT NULL           -- equals decision unless a person overturned it
);

CREATE TABLE IF NOT EXISTS appeals (
  ticket        TEXT PRIMARY KEY,
  app_id        TEXT NOT NULL UNIQUE REFERENCES applications(id),
  text          TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'upheld', 'overturned')),
  created_at    TEXT NOT NULL,
  reviewer_note TEXT,
  resolved_at   TEXT
);

CREATE TABLE IF NOT EXISTS audit (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  app_id    TEXT,
  ts        TEXT NOT NULL,
  step      TEXT NOT NULL,
  component TEXT NOT NULL,
  details   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_app ON audit(app_id);
CREATE INDEX IF NOT EXISTS apps_user ON applications(user_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(conn: sqlite3.Connection | None = None) -> None:
    conn = conn or connect()
    conn.executescript(SCHEMA)
    conn.commit()


def log(app_id: str | None, step: str, component: str, details: str, ts: str | None = None) -> None:
    """Append one line to the audit log. Never pass names or contact details here."""
    db = get_db()
    db.execute("INSERT INTO audit (app_id, ts, step, component, details) VALUES (?, ?, ?, ?, ?)",
               (app_id, ts or now_iso(), step, component, details))


def loads(value):
    return json.loads(value) if value else None
