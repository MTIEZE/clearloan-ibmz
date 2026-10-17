"""Risk model: an explainable logistic scorecard on the UCI "Default of Credit Card Clients" features.

Two variants, like the datathon notebook:
  full_history         applicant has a repayment record (PAY_0..PAY_6 columns)
  first_time_borrower  no history: those columns are dropped and the model is less sure

Every term of the score is additive, so each feature's contribution to the risk is exact (no
approximation is needed to explain it). The weights can be replaced by the ones exported from the
trained model without touching the rest of the back-end.
"""
import math

from . import config

VERSION = "scorecard-1.3"

INTERCEPT = -0.55
REF_RATIO = 0.35          # payments covering 35% of bills is neutral
REF_MONTHS = 8.0          # a loan worth 8 months of bills is neutral
W_RATIO = -4.0
W_MONTHS = 0.07
W_NO_HISTORY = 0.35
W_LATE_MONTH = 0.35
W_SEVERE_LATE = 0.5
W_ALL_ON_TIME = -0.45
W_EDUCATION = {"graduate_school": -0.15, "university": -0.05, "high_school": 0.10, "other": 0.10}


def _features(f: dict) -> dict:
    bill, pay = f["avg_bill"], f["avg_payment"]
    ratio = pay / bill if bill > 0 else (1.5 if pay > 0 else 1.0)
    history = f["pay_history"] if f["credit_history"] else []
    return {
        "ratio": min(max(ratio, 0.0), 1.5),
        "months": min(f["loan_amount"] / max(bill, 500), 60.0),
        "late": sum(1 for p in history if p > 0),
        "severe": any(p >= 2 for p in history),
    }


def _contributions(f: dict) -> list[dict]:
    x = _features(f)
    out = [
        {"feature": "payment_ratio", "value": round(x["ratio"], 2), "c": W_RATIO * (x["ratio"] - REF_RATIO)},
        {"feature": "loan_amount", "value": f["loan_amount"], "months": round(x["months"], 1),
         "c": W_MONTHS * (x["months"] - REF_MONTHS)},
    ]
    if not f["credit_history"]:
        out.append({"feature": "credit_history", "value": "none", "c": W_NO_HISTORY})
    elif x["late"]:
        out.append({"feature": "repayment_record", "value": x["late"],
                    "c": W_LATE_MONTH * x["late"] + (W_SEVERE_LATE if x["severe"] else 0)})
    else:
        out.append({"feature": "repayment_record", "value": 0, "c": W_ALL_ON_TIME})
    # Age is collected (UCI feature) but has no weight: the fairness audit compares age bands.
    out.append({"feature": "education", "value": f["education"], "c": W_EDUCATION.get(f["education"], 0.1)})
    return out


def _risk(f: dict) -> int:
    logit = INTERCEPT + sum(t["c"] for t in _contributions(f))
    return max(1, min(99, round(100 / (1 + math.exp(-logit)))))


def _label(t: dict, f: dict) -> str:
    raises = t["c"] > 0
    match t["feature"]:
        case "payment_ratio":
            pct = round(t["value"] * 100)
            return (f"Your monthly payments cover only {pct}% of your monthly bills" if raises
                    else f"Your monthly payments cover {pct}% of your monthly bills")
        case "loan_amount":
            return (f"AED {f['loan_amount']:,.0f} is about {t['months']:g} months of your bills" if raises
                    else f"AED {f['loan_amount']:,.0f} is modest next to your bills ({t['months']:g} months)")
        case "credit_history":
            return "No credit history yet, so the model is less sure"
        case "repayment_record":
            n = t["value"]
            return f"{n} late payment{'s' if n > 1 else ''} in the last 6 months" if n else "6 months of on-time payments"
        case _:
            return "Education level has a small effect"


def score(f: dict) -> dict:
    """Decision, risk score (0-100) and the reasons ranked by how much they moved the score."""
    risk = _risk(f)
    terms = sorted(_contributions(f), key=lambda t: abs(t["c"]), reverse=True)
    reasons = []
    for t in terms:
        if abs(t["c"]) < 0.05 or len(reasons) == 4:
            continue
        size = abs(t["c"])
        reasons.append({
            "feature": t["feature"],
            "value": t["value"],
            "impact": "high" if size >= 0.6 else "medium" if size >= 0.25 else "low",
            "direction": "raises" if t["c"] > 0 else "lowers",
            "weight": round(min(1.0, size / 1.2), 2),
            "label": _label(t, f),
        })
    return {
        "decision": "approved" if risk <= config.APPROVAL_LIMIT else "not_approved",
        "risk_score": risk,
        "top_reasons": reasons,
        "version": VERSION,
    }


def counterfactuals(f: dict) -> dict:
    """Smallest single change that would turn the decision into an approval, when one exists."""
    limit = config.APPROVAL_LIMIT
    out = {"max_loan": None, "min_payment": None, "combo": None}

    def passes(**change):
        return _risk({**f, **change}) <= limit

    # Largest loan (in steps of 500) that passes with today's payments
    lo, hi = 1000, int(f["loan_amount"])
    if passes(loan_amount=lo):
        while hi - lo > 500:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if passes(loan_amount=mid) else (lo, mid)
        out["max_loan"] = lo // 500 * 500

    # Smallest monthly payment (in steps of 50) that passes for the same loan
    def min_payment(loan):
        lo, hi = int(f["avg_payment"]), int(max(f["avg_bill"], 1) * 1.5)
        if not passes(loan_amount=loan, avg_payment=hi):
            return None
        while hi - lo > 50:
            mid = (lo + hi) // 2
            lo, hi = (lo, mid) if passes(loan_amount=loan, avg_payment=mid) else (mid, hi)
        return -(-hi // 50) * 50

    out["min_payment"] = min_payment(f["loan_amount"])
    if out["max_loan"] is None and out["min_payment"] is None:
        half = max(1000, int(f["loan_amount"] / 2) // 500 * 500)
        pay = min_payment(half)
        if pay is not None:
            out["combo"] = {"loan": half, "payment": pay}
    return out
