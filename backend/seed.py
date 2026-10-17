"""Demo accounts and sample applications, for local development only.

Demo accounts (local only, change them before any real use):
  Applicant   demo@clearloan.test     / ClearLoan-Demo-2026
  Bank staff  auditor@clearloan.test  / ClearLoan-Staff-2026  + 6-digit code: `python -m backend totp auditor@clearloan.test`
              (or add DEMO_TOTP_SECRET below to any authenticator app)
"""
import random

from . import security, service
from .db import get_db, now_iso

DEMO_APPLICANT = ("demo@clearloan.test", "ClearLoan-Demo-2026", "Sara")
DEMO_STAFF = ("auditor@clearloan.test", "ClearLoan-Staff-2026", "Auditor")
DEMO_TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
SAMPLE_USER = ("samples@clearloan.test", None, "Sample")

FIRST = ["Ahmed", "Fatima", "Omar", "Aisha", "Ravi", "Priya", "Bilal", "Mariam", "Jean", "Chloé", "Yusuf", "Noor"]
LAST = ["Khan", "Haddad", "Sharma", "Al Mansoori", "Dubois", "Iqbal", "Nair", "Rahman", "Martin", "Saleh"]


def add_user(email, password, name, role="applicant", totp_secret=None) -> int:
    db = get_db()
    row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        return row["id"]
    # Accounts without a password (sample owner) get a random one nobody knows
    pw = password or security.new_totp_secret()
    db.execute("INSERT INTO users (email, password_hash, role, display_name, totp_secret, created_at) VALUES (?, ?, ?, ?, ?, ?)",
               (email, security.hash_password(pw), role, name, totp_secret, now_iso()))
    db.commit()
    return db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]


def seed_accounts() -> None:
    add_user(*DEMO_APPLICANT)
    add_user(*DEMO_STAFF, role="staff", totp_secret=DEMO_TOTP_SECRET)


def seed_samples(n: int = 48, seed: int = 7) -> int:
    """Run `n` synthetic applicants through the real pipeline, so the dashboards have data."""
    rnd = random.Random(seed)
    owner = add_user(*SAMPLE_USER)
    made = []
    for i in range(n):
        bill = rnd.choice([1800, 2400, 3200, 4000, 5200, 6500, 8000])
        has_history = rnd.random() < 0.6
        body = {
            "identity": {"name": f"{rnd.choice(FIRST)} {rnd.choice(LAST)}",
                         "id_number": f"784-19{rnd.randint(50, 99)}-{rnd.randint(1000000, 9999999)}-{rnd.randint(1, 9)}",
                         "phone": f"+971 5{rnd.randint(0, 8)} {rnd.randint(100, 999)} {rnd.randint(1000, 9999)}",
                         "email": f"sample{i}@example.test"},
            "financial": {"loan_amount": rnd.choice([5000, 10000, 15000, 20000, 30000, 45000, 60000]),
                          "avg_bill": bill, "avg_payment": round(bill * rnd.uniform(0.1, 0.75) / 50) * 50,
                          "age": rnd.randint(21, 66),
                          "education": rnd.choice(["university", "graduate_school", "high_school", "other"]),
                          "marriage": rnd.choice(["single", "married", "other"]),
                          "credit_history": has_history,
                          "pay_history": [rnd.choice([0, 0, 0, 0, 1, 2]) for _ in range(6)] if has_history else []},
            "audit": {"sex": rnd.choice(["male", "female", "female", "male", "undisclosed"])},
            "language": rnd.choice(["en", "en", "ar", "fr", "ur", "hi"]),
        }
        made.append(service.process_application(owner, body))

    # A few people ask for a human review
    db = get_db()
    rejected = [r["id"] for r in db.execute(
        f"SELECT id FROM applications WHERE decision = 'not_approved' AND id IN ({','.join('?' * len(made))})", made)]
    for app_id in rejected[:4]:
        db.execute("INSERT OR IGNORE INTO appeals (ticket, app_id, text, created_at) VALUES (?, ?, ?, ?)",
                   (service.new_ticket(), app_id,
                    "Dear ClearLoan team,\nI started a new job last month with a higher salary. "
                    "I can share my contract and payslips.\nThank you", now_iso()))
    db.commit()
    return len(made)
