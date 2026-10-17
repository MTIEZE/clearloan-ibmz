"""Fairness: the offline report from training, plus live monitoring of the decisions made on this server."""
import json
from pathlib import Path

from .db import get_db

REPORT = Path(__file__).parent / "data" / "fairness_report.json"
AGE_BANDS = [("18 to 25", 0, 25), ("26 to 35", 26, 35), ("36 to 50", 36, 50), ("51 and over", 51, 200)]
SEX_LABELS = {"male": "Men", "female": "Women", "undisclosed": "Not said"}
MIN_GROUP = 10      # smaller groups are shown but left out of gaps and ratios (too noisy)


def age_band(age: int) -> str:
    return next(label for label, lo, hi in AGE_BANDS if lo <= age <= hi)


def _rates(rows, key, labels):
    out = []
    for label in labels:
        group = [r for r in rows if r[key] == label]
        if group:
            approved = sum(1 for r in group if r["decision"] == "approved")
            out.append({"label": SEX_LABELS.get(label, label), "n": len(group), "rate": round(100 * approved / len(group)),
                        "enough": len(group) >= MIN_GROUP})
    return out


def live() -> dict:
    """Metrics computed from the model's own decisions (before any human review)."""
    db = get_db()
    rows = db.execute("SELECT decision, final_decision, audit_sex, age_band, latency_ms, model_used FROM applications").fetchall()
    appeals = db.execute("SELECT status, COUNT(*) AS n FROM appeals GROUP BY status").fetchall()
    by_status = {r["status"]: r["n"] for r in appeals}
    n = len(rows)
    sex = _rates(rows, "audit_sex", ["male", "female", "undisclosed"])
    age = _rates(rows, "age_band", [label for label, *_ in AGE_BANDS])
    men = next((g["rate"] for g in sex if g["label"] == "Men" and g["enough"]), None)
    women = next((g["rate"] for g in sex if g["label"] == "Women" and g["enough"]), None)
    age_rates = [g["rate"] for g in age if g["enough"]]
    return {
        "applications": n,
        "approval_rate": round(100 * sum(1 for r in rows if r["decision"] == "approved") / n) if n else None,
        "gap_sex": abs(men - women) if men is not None and women is not None else None,
        "ratio_age": round(min(age_rates) / max(age_rates), 2) if len(age_rates) > 1 and max(age_rates) else None,
        "avg_latency_ms": round(sum(r["latency_ms"] for r in rows) / n) if n else None,
        "first_time_share": round(100 * sum(1 for r in rows if r["model_used"] == "first_time_borrower") / n) if n else None,
        "groups": {"sex": sex, "age": age},
        "appeals": {"open": by_status.get("open", 0), "upheld": by_status.get("upheld", 0),
                    "overturned": by_status.get("overturned", 0)},
        "small_sample": n < 30,
        "min_group": MIN_GROUP,
    }


def report() -> dict:
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    data["live"] = live()
    return data
