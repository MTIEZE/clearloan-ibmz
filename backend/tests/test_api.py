import os
import tempfile

# Isolated keys and database for the tests (must be set before the back-end is imported)
_tmp = tempfile.mkdtemp(prefix="clearloan-test-")
os.environ["CLEARLOAN_INSTANCE"] = _tmp

import pytest  # noqa: E402

from backend import model, security  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.gateway import pii_scan, redact  # noqa: E402
from backend.seed import DEMO_APPLICANT, DEMO_STAFF, DEMO_TOTP_SECRET, seed_accounts  # noqa: E402

H = {"X-ClearLoan": "1"}

APPLICATION = {
    "identity": {"name": "Ahmed Khan", "id_number": "784-1990-1234567-1", "phone": "+971 50 123 4567",
                 "email": "ahmed.khan@example.com"},
    "financial": {"loan_amount": 50000, "avg_bill": 3200, "avg_payment": 600, "age": 24, "education": "university",
                  "marriage": "single", "credit_history": False, "pay_history": []},
    "audit": {"sex": "male"},
    "language": "fr",
}


@pytest.fixture()
def app():
    db = os.path.join(_tmp, f"t{os.urandom(4).hex()}.sqlite3")
    app = create_app({"TESTING": True, "DATABASE": db})
    with app.app_context():
        seed_accounts()
    return app


def login(client, who="applicant"):
    email, password, _ = DEMO_APPLICANT if who == "applicant" else DEMO_STAFF
    body = {"email": email, "password": password, "role": who}
    if who == "staff":
        body["code"] = security.totp(DEMO_TOTP_SECRET)
    return client.post("/api/login", json=body, headers=H).get_json()


def test_pages_served_but_not_source(app):
    c = app.test_client()
    assert c.get("/").status_code == 200
    assert c.get("/apply.html").status_code == 200
    assert c.get("/assets/css/style.css").status_code == 200
    assert c.get("/backend/config.py").status_code == 404
    assert c.get("/instance/secret.key").status_code == 404


def test_csrf_header_required(app):
    c = app.test_client()
    assert c.post("/api/login", json={"email": "x@y.z"}).status_code == 400


def test_login_lockout(app):
    c = app.test_client()
    for i in range(4):
        r = c.post("/api/login", json={"email": "demo@clearloan.test", "password": "wrong-pass", "role": "applicant"}, headers=H).get_json()
        assert r == {"ok": False, "error": "invalid", "attempts_left": 4 - i}
    r = c.post("/api/login", json={"email": "demo@clearloan.test", "password": "wrong-pass", "role": "applicant"}, headers=H).get_json()
    assert r["error"] == "locked"
    # Even the right password is refused while locked
    assert login(c)["error"] == "locked"


def test_staff_needs_code(app):
    c = app.test_client()
    email, password, _ = DEMO_STAFF
    r = c.post("/api/login", json={"email": email, "password": password, "role": "staff", "code": "000000"}, headers=H).get_json()
    assert r["ok"] is False
    assert login(c, "staff")["ok"] is True


def test_full_applicant_flow_and_privacy(app):
    c = app.test_client()
    assert c.post("/api/apply", json=APPLICATION, headers=H).status_code == 401
    assert login(c)["ok"]
    r = c.post("/api/apply", json=APPLICATION, headers=H)
    assert r.status_code == 201
    d = r.get_json()
    assert d["model"]["decision"] == "not_approved"
    assert d["display_name"] == "Ahmed"
    assert d["llm"]["explanation"].startswith("Bonjour Ahmed")
    assert d["llm"]["explanation_en"].startswith("Hello Ahmed")
    assert len(d["llm"]["steps"]) == 3

    p = c.get(f"/api/privacy/{d['application_id']}").get_json()
    assert p["pii_scan"]["personal_fields_found"] == 0
    assert "Ahmed" not in p["prompt"] and "123" not in p["prompt"].split("AED")[0]
    assert p["model_input"]["applicant"] == d["token"]
    assert "sex" not in p["model_input"]

    a = c.post(f"/api/appeal/{d['application_id']}", json={"text": "Ahmed here, I have a new job. Call +971 50 123 4567"}, headers=H).get_json()
    assert a["ok"] and a["ticket"].startswith("RV-")
    assert c.post(f"/api/appeal/{d['application_id']}", json={"text": "again please, thanks"}, headers=H).status_code == 409

    # Staff: sees the review without the name or phone, and can overturn it
    s = app.test_client()
    login(s, "staff")
    item = next(i for i in s.get("/api/reviews").get_json()["items"] if i["application_id"] == d["application_id"])
    assert "Ahmed" not in item["text"] and "4567" not in item["text"]
    assert s.post(f"/api/reviews/{item['ticket']}", json={"outcome": "overturned", "note": "New contract checked."}, headers=H).get_json()["ok"]
    after = c.get(f"/api/applications/{d['application_id']}").get_json()
    assert after["final_decision"] == "approved" and after["appeal"]["status"] == "overturned"


def test_roles_and_ownership(app):
    owner = app.test_client()
    login(owner)
    app_id = owner.post("/api/apply", json=APPLICATION, headers=H).get_json()["application_id"]

    other = app.test_client()
    other.post("/api/register", json={"email": "other@clearloan.test", "password": "another-pass-1", "display_name": "Lina"}, headers=H)
    assert other.get(f"/api/privacy/{app_id}").status_code == 404
    assert other.get("/api/fairness").status_code == 403

    staff = app.test_client()
    login(staff, "staff")
    p = staff.get(f"/api/privacy/{app_id}").get_json()
    assert p["identity_masked"]["name"] is None and p["identity_masked"]["email"] is None
    assert staff.get(f"/api/applications/{app_id}").get_json()["display_name"] is None
    assert staff.post("/api/apply", json=APPLICATION, headers=H).status_code == 403
    live = staff.get("/api/fairness").get_json()["live"]
    assert live["applications"] == 1


def test_validation(app):
    c = app.test_client()
    login(c)
    bad = {**APPLICATION, "financial": {**APPLICATION["financial"], "age": 16}}
    r = c.post("/api/apply", json=bad, headers=H)
    assert r.status_code == 400 and r.get_json()["field"] == "age"


def test_model_and_counterfactuals():
    good = {"loan_amount": 20000, "avg_bill": 3000, "avg_payment": 1500, "age": 35, "education": "university",
            "marriage": "married", "credit_history": True, "pay_history": [0] * 6}
    assert model.score(good)["decision"] == "approved"
    weak = APPLICATION["financial"]
    s = model.score(weak)
    assert s["decision"] == "not_approved" and s["top_reasons"][0]["feature"] == "payment_ratio"
    cf = model.counterfactuals(weak)
    assert cf["min_payment"] and model.score({**weak, "avg_payment": cf["min_payment"]})["decision"] == "approved"


def test_pii_tools():
    ident = APPLICATION["identity"]
    assert pii_scan("Applicant_7F3A was approved for AED 50,000", ident) == []
    assert set(pii_scan("Ahmed, call +971 50 123 4567 or ahmed.khan@example.com", ident)) == {"name", "phone", "email"}
    assert redact("I am Ahmed Khan, 784-1990-1234567-1", ident) == "I am [name] [name], [id number]"
