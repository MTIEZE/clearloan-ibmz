"""Application pipeline: web app → privacy gateway → risk model → LLM → privacy gateway."""
import json
import re
import secrets
import time
from datetime import datetime

from . import config, gateway, llm, model
from .db import get_db, loads, log, now_iso
from .fairness import age_band

EDUCATION = {"university", "graduate_school", "high_school", "other"}
MARRIAGE = {"single", "married", "other"}
SEX = {"male", "female", "undisclosed"}
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class Invalid(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


def _text(d: dict, key: str, lo: int, hi: int, label: str) -> str:
    value = d.get(key)
    if not isinstance(value, str) or not lo <= len(value.strip()) <= hi:
        raise Invalid(key, f"{label} is missing or too long.")
    return value.strip()


def _num(d: dict, key: str, lo: float, hi: float, label: str) -> float:
    value = d.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
        raise Invalid(key, f"{label} must be between {lo:,.0f} and {hi:,.0f}.")
    return float(value)


def validate(body: dict) -> tuple[dict, dict, dict, str]:
    if not isinstance(body, dict):
        raise Invalid("body", "Expected a JSON object.")
    ident, fin, audit = (body.get(k) if isinstance(body.get(k), dict) else {} for k in ("identity", "financial", "audit"))
    identity = {
        "name": _text(ident, "name", 2, 100, "Full name"),
        "id_number": _text(ident, "id_number", 5, 30, "ID number"),
        "phone": _text(ident, "phone", 6, 25, "Phone number"),
        "email": _text(ident, "email", 5, 254, "Email"),
    }
    if not re.search(r"[^\W\d_]", identity["name"]):
        raise Invalid("name", "Full name must contain letters.")
    if len(re.sub(r"\D", "", identity["phone"])) < 7:
        raise Invalid("phone", "Phone number looks too short.")
    if not EMAIL_RE.match(identity["email"]):
        raise Invalid("email", "Email address is not valid.")

    has_history = fin.get("credit_history") is True
    history = fin.get("pay_history") if has_history else []
    if has_history and (not isinstance(history, list) or len(history) != 6
                        or any(isinstance(p, bool) or p not in (0, 1, 2) for p in history)):
        raise Invalid("pay_history", "Repayment record must have 6 months.")
    financial = {
        "loan_amount": _num(fin, "loan_amount", 1000, 5_000_000, "Loan amount"),
        "avg_bill": _num(fin, "avg_bill", 0, 1_000_000, "Monthly bills"),
        "avg_payment": _num(fin, "avg_payment", 0, 1_000_000, "Monthly payments"),
        "age": int(_num(fin, "age", 18, 100, "Age")),
        "education": fin.get("education") if fin.get("education") in EDUCATION else None,
        "marriage": fin.get("marriage") if fin.get("marriage") in MARRIAGE else None,
        "credit_history": has_history,
        "pay_history": [int(p) for p in history],
    }
    if not financial["education"]:
        raise Invalid("education", "Please choose an education level.")
    if not financial["marriage"]:
        raise Invalid("marriage", "Please choose a marital status.")
    sex = audit.get("sex") if audit.get("sex") in SEX else "undisclosed"
    language = body.get("language") if body.get("language") in config.LANGUAGES else "en"
    return identity, financial, {"sex": sex}, language


def _first_name(name: str) -> str:
    first = re.sub(r"[^\w'-]", "", name.split()[0])[:40]
    return first[:1].upper() + first[1:] if first else "Applicant"


def process_application(user_id: int, body: dict) -> str:
    """Run the whole pipeline and store the result. Returns the application id."""
    t0 = time.perf_counter()
    identity, f, audit, language = validate(body)
    db = get_db()
    while True:
        app_id, token = gateway.new_ids()
        if not db.execute("SELECT 1 FROM applications WHERE id = ?", (app_id,)).fetchone():
            break

    log(app_id, "Application received", "Web app", "Form received by the server")
    identity_enc = gateway.encrypt_identity(identity)
    masked = gateway.mask_identity(identity)
    first = _first_name(identity["name"])
    log(app_id, "Identity hidden", "Privacy gateway", f"4 fields encrypted → {token}")

    model_used = "full_history" if f["credit_history"] else "first_time_borrower"
    result = model.score(f)
    cf = model.counterfactuals(f) if result["decision"] != "approved" else {}
    log(app_id, "Risk scored", f"{result['version']} · {model_used.replace('_', ' ')}",
        f"{result['risk_score']}/100 · {result['decision'].replace('_', ' ')}")

    prompt = llm.build_prompt(token, result, f, language)
    found = gateway.pii_scan(prompt, identity)
    if found:   # never expected: the prompt is built from the token only. Block the LLM call if it happens.
        log(app_id, "Prompt blocked", "Privacy gateway", f"Personal data found: {', '.join(found)}")
        prompt = "[blocked by privacy gateway]"
        text = {"explanation": llm.template_explanation(language, token, result, f),
                "explanation_en": None if language == "en" else llm.template_explanation("en", token, result, f),
                "steps": llm.template_steps(language, result, f, cf), "language": language, "engine": "ClearLoan explainer (templates)"}
    else:
        text = llm.explain(token, result, f, cf, language, prompt)
        log(app_id, "Explanation written", text["engine"], "Prompt scan: 0 personal fields")
    text["appeal_draft"] = llm.appeal_draft(app_id, token)

    latency = round((time.perf_counter() - t0) * 1000)
    db.execute(
        "INSERT INTO applications (id, token, user_id, created_at, identity_enc, identity_masked, first_name, audit_sex,"
        " age_band, financial, language, model_used, decision, risk_score, reasons, llm, prompt, pii_found, latency_ms,"
        " final_decision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (app_id, token, user_id, now_iso(), identity_enc, json.dumps(masked), first, audit["sex"], age_band(f["age"]),
         json.dumps(f), language, model_used, result["decision"], result["risk_score"],
         json.dumps({"top_reasons": result["top_reasons"], "version": result["version"], "counterfactuals": cf}),
         json.dumps(text), prompt, len(found), latency, result["decision"]))
    log(app_id, "Name restored", "Privacy gateway", "First name shown to the applicant only")
    db.commit()
    return app_id


# ---------- Read models

def _appeal(app_id: str, for_staff: bool, identity: dict | None = None) -> dict | None:
    a = get_db().execute("SELECT * FROM appeals WHERE app_id = ?", (app_id,)).fetchone()
    if not a:
        return None
    text = a["text"]
    if for_staff and identity:
        text = gateway.redact(text, identity)
    return {"ticket": a["ticket"], "status": a["status"], "created_at": a["created_at"], "text": text,
            "reviewer_note": a["reviewer_note"], "resolved_at": a["resolved_at"]}


def result_payload(row, for_staff: bool = False) -> dict:
    """The decision as the applicant sees it (first name restored), or as staff see it (token only)."""
    text = loads(row["llm"])
    reasons = loads(row["reasons"])
    f = loads(row["financial"])
    name = None if for_staff else row["first_name"]

    def restore(s):
        return gateway.restore_name(s, row["token"], name) if (s and name) else s

    return {
        "application_id": row["id"],
        "token": row["token"],
        "created_at": row["created_at"],
        "latency_ms": row["latency_ms"],
        "model_used": row["model_used"],
        "display_name": name,
        "request": {"loan_amount": f["loan_amount"], "language": row["language"]},
        "model": {"decision": row["decision"], "risk_score": row["risk_score"],
                  "top_reasons": reasons["top_reasons"], "version": reasons["version"],
                  "limit": config.APPROVAL_LIMIT},
        "final_decision": row["final_decision"],
        "llm": {
            "explanation": restore(text["explanation"]),
            "explanation_en": restore(text["explanation_en"]),
            "steps": [restore(s) for s in text["steps"]],
            "appeal_draft": restore(text["appeal_draft"]),
            "language": text["language"],
            "engine": text["engine"],
        },
        "appeal": _appeal(row["id"], for_staff, gateway.decrypt_identity(row["identity_enc"]) if for_staff else None),
    }


def summary(row, for_staff: bool) -> dict:
    f = loads(row["financial"])
    a = get_db().execute("SELECT status FROM appeals WHERE app_id = ?", (row["id"],)).fetchone()
    out = {"application_id": row["id"], "token": row["token"], "created_at": row["created_at"],
           "loan_amount": f["loan_amount"], "risk_score": row["risk_score"], "decision": row["decision"],
           "final_decision": row["final_decision"], "model_used": row["model_used"],
           "appeal_status": a["status"] if a else None}
    if not for_staff:
        out.pop("token")
    return out


def _clock(ts: str) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M:%S.%f")[:12]


def privacy_payload(row, for_staff: bool) -> dict:
    f = loads(row["financial"])
    masked = loads(row["identity_masked"])
    if for_staff:   # staff never see names or contact details, even masked
        masked = {"name": None, "id_number": masked["id_number"], "phone": None, "email": None}
    audit = get_db().execute("SELECT ts, step, component, details FROM audit WHERE app_id = ? ORDER BY id",
                             (row["id"],)).fetchall()
    return {
        "application_id": row["id"],
        "token": row["token"],
        "identity_masked": masked,
        "audit_only": {"sex": row["audit_sex"]},
        "model_input": {"applicant": row["token"], **{k: f[k] for k in (
            "loan_amount", "age", "education", "marriage", "avg_bill", "avg_payment", "credit_history")},
            "pay_history": f["pay_history"] if f["credit_history"] else None},
        "prompt": row["prompt"],
        "pii_scan": {"personal_fields_found": row["pii_found"]},
        "engine": loads(row["llm"])["engine"],
        "audit_log": [{"ts": a["ts"], "time": _clock(a["ts"]), "step": a["step"], "component": a["component"],
                       "details": a["details"]} for a in audit],
    }


def new_ticket() -> str:
    return "RV-" + secrets.token_hex(3).upper()[:5]
