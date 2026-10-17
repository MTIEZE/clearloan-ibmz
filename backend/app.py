"""ClearLoan Flask app: serves the front-end pages and the /api/* routes (contract in README.md)."""
import re

from flask import Flask, abort, jsonify, request, send_from_directory, session
from werkzeug.exceptions import HTTPException

from . import config, fairness, gateway, model, security, service
from .db import close_db, get_db, init_db, log, now_iso

PAGES = {"index.html", "apply.html", "decision.html", "privacy.html", "fairness.html", "reviews.html"}


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        SESSION_COOKIE_NAME="cl_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=config.COOKIE_SECURE,
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    app.json.sort_keys = False      # keep fields in the order of the contract (applicant first)
    if test_config:
        app.config.update(test_config)
        if "DATABASE" in test_config:
            config.DATABASE = test_config["DATABASE"]

    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    # ---------- Cross-cutting

    @app.before_request
    def guard_api():
        if request.path.startswith("/api/") and not security.csrf_ok():
            return jsonify(ok=False, error="bad_request", message="JSON with the X-ClearLoan header required."), 400

    @app.after_request
    def headers(res):
        for k, v in security.SECURITY_HEADERS.items():
            res.headers.setdefault(k, v)
        if request.path.startswith("/api/"):
            res.headers["Cache-Control"] = "no-store"
        else:   # pages and assets: always revalidate (cheap thanks to ETags), so updates show at once
            res.headers["Cache-Control"] = "no-cache"
        return res

    @app.errorhandler(HTTPException)
    def http_error(e):
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error=e.name.lower().replace(" ", "_"), message=e.description), e.code
        return e

    @app.errorhandler(service.Invalid)
    def invalid(e):
        return jsonify(ok=False, error="invalid", field=e.field, message=str(e)), 400

    def body() -> dict:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    def own_application(app_id: str, user: dict):
        """Applicants can open only their own files. Staff can open any (without identity)."""
        row = get_db().execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        if not row or (user["role"] == "applicant" and row["user_id"] != user["id"]):
            abort(404, "No application found with this ID.")
        return row

    # ---------- Pages

    @app.get("/")
    def home():
        return send_from_directory(config.ROOT, "index.html")

    @app.get("/<page>")
    def page(page):
        if page not in PAGES:
            abort(404)
        return send_from_directory(config.ROOT, page)

    @app.get("/assets/<path:path>")
    def assets(path):
        return send_from_directory(config.ROOT / "assets", path)

    # ---------- Auth

    @app.get("/api/health")
    def health():
        return jsonify(ok=True, model=model.VERSION,
                       llm=f"IBM Granite via Ollama ({config.GRANITE_MODEL})" if config.OLLAMA_URL else "templates")

    @app.post("/api/register")
    def register():
        d = body()
        email = str(d.get("email", "")).strip().lower()
        password = d.get("password") if isinstance(d.get("password"), str) else ""
        name = re.sub(r"\s+", " ", str(d.get("display_name", "")).strip())[:40]
        if not service.EMAIL_RE.match(email) or len(email) > 254:
            return jsonify(ok=False, error="invalid", field="email", message="Email address is not valid."), 400
        if not 8 <= len(password) <= 128:
            return jsonify(ok=False, error="invalid", field="password", message="Password must have 8 to 128 characters."), 400
        if not name:
            return jsonify(ok=False, error="invalid", field="display_name", message="Please enter your first name."), 400
        db = get_db()
        if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            return jsonify(ok=False, error="exists", message="An account already uses this email."), 409
        db.execute("INSERT INTO users (email, password_hash, role, display_name, created_at) VALUES (?, ?, 'applicant', ?, ?)",
                   (email, security.hash_password(password), name, now_iso()))
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        log(None, "Account created", "Auth", f"applicant · {gateway.mask_email(email)}")
        db.commit()
        security.start_session(user)
        return jsonify(ok=True, role="applicant", display_name=user["display_name"]), 201

    @app.post("/api/login")
    def login():
        d = body()
        email = str(d.get("email", "")).strip().lower()
        role = d.get("role") if d.get("role") in ("applicant", "staff") else "applicant"
        masked = gateway.mask_email(email)
        db = get_db()
        minutes = security.lock_status(email)
        if minutes:
            return jsonify(ok=False, error="locked", minutes_left=minutes)
        user = security.check_credentials(email, d.get("password"), role, d.get("code"))
        if not user:
            left = security.record_failure(email)
            log(None, "Sign-in failed", "Auth", f"{role} · {masked}")
            db.commit()
            if left == 0:
                return jsonify(ok=False, error="locked", minutes_left=config.LOCK_MINUTES)
            return jsonify(ok=False, error="invalid", attempts_left=left)
        security.clear_failures(email)
        log(None, "Signed in", "Auth", f"{role} · {masked}")
        db.commit()
        security.start_session(user)
        return jsonify(ok=True, role=user["role"], display_name=user["display_name"])

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/me")
    def me():
        # 200 either way: "not signed in" is a normal answer here, not an error
        user = security.current_user()
        if not user:
            return jsonify(ok=False, error="signed_out")
        return jsonify(ok=True, role=user["role"], display_name=user["display_name"],
                       session_minutes=config.SESSION_MINUTES)

    # ---------- Applicant

    @app.post("/api/apply")
    @security.require("applicant")
    def apply(user):
        app_id = service.process_application(user["id"], body())
        row = get_db().execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        return jsonify(service.result_payload(row)), 201

    @app.get("/api/applications")
    @security.require("applicant", "staff")
    def applications(user):
        staff = user["role"] == "staff"
        sql = "SELECT * FROM applications" + ("" if staff else " WHERE user_id = ?") + " ORDER BY created_at DESC LIMIT 100"
        rows = get_db().execute(sql, () if staff else (user["id"],)).fetchall()
        return jsonify(items=[service.summary(r, staff) for r in rows])

    @app.get("/api/applications/<app_id>")
    @security.require("applicant", "staff")
    def application(app_id, user):
        return jsonify(service.result_payload(own_application(app_id, user), for_staff=user["role"] == "staff"))

    @app.get("/api/privacy/<app_id>")
    @security.require("applicant", "staff")
    def privacy(app_id, user):
        return jsonify(service.privacy_payload(own_application(app_id, user), for_staff=user["role"] == "staff"))

    @app.post("/api/appeal/<app_id>")
    @security.require("applicant")
    def appeal(app_id, user):
        row = own_application(app_id, user)
        text = str(body().get("text", "")).strip()
        if not 10 <= len(text) <= 4000:
            return jsonify(ok=False, error="invalid", field="text", message="Please write 10 to 4,000 characters."), 400
        if "[Add your reason here" in text:     # the draft from llm.appeal_draft, sent unchanged
            return jsonify(ok=False, error="invalid", field="text", message="Replace the line in [brackets] with your reason."), 400
        if row["final_decision"] == "approved":
            return jsonify(ok=False, error="approved", message="This application is already approved."), 409
        db = get_db()
        if db.execute("SELECT 1 FROM appeals WHERE app_id = ?", (app_id,)).fetchone():
            return jsonify(ok=False, error="exists", message="A review was already requested for this application."), 409
        ticket = service.new_ticket()
        db.execute("INSERT INTO appeals (ticket, app_id, text, created_at) VALUES (?, ?, ?, ?)",
                   (ticket, app_id, text, now_iso()))
        log(app_id, "Human review requested", "Applicant", f"Ticket {ticket}")
        db.commit()
        return jsonify(ok=True, ticket=ticket, reviewer="Credit officer", eta_hours=48, status="open")

    # ---------- Staff

    @app.get("/api/reviews")
    @security.require("staff")
    def reviews(user):
        rows = get_db().execute(
            "SELECT a.ticket, a.status, a.created_at, a.app_id FROM appeals a "
            "ORDER BY (a.status = 'open') DESC, a.created_at DESC LIMIT 200").fetchall()
        items = []
        for r in rows:
            app_row = get_db().execute("SELECT * FROM applications WHERE id = ?", (r["app_id"],)).fetchone()
            payload = service.result_payload(app_row, for_staff=True)
            f = service.loads(app_row["financial"])
            items.append({**payload["appeal"], "application_id": r["app_id"], "token": app_row["token"],
                          "model": payload["model"], "final_decision": app_row["final_decision"],
                          "model_used": app_row["model_used"],
                          "financial": {k: f[k] for k in ("loan_amount", "avg_bill", "avg_payment", "credit_history")}})
        return jsonify(items=items)

    @app.post("/api/reviews/<ticket>")
    @security.require("staff")
    def resolve(ticket, user):
        d = body()
        outcome = d.get("outcome")
        note = str(d.get("note", "")).strip()[:1000]
        if outcome not in ("upheld", "overturned"):
            return jsonify(ok=False, error="invalid", field="outcome", message="Choose upheld or overturned."), 400
        if len(note) < 5:
            return jsonify(ok=False, error="invalid", field="note", message="Please explain the outcome to the applicant."), 400
        db = get_db()
        a = db.execute("SELECT * FROM appeals WHERE ticket = ?", (ticket,)).fetchone()
        if not a:
            abort(404, "No review with this ticket.")
        if a["status"] != "open":
            return jsonify(ok=False, error="closed", message="This review is already closed."), 409
        app_row = db.execute("SELECT identity_enc FROM applications WHERE id = ?", (a["app_id"],)).fetchone()
        note = gateway.redact(note, gateway.decrypt_identity(app_row["identity_enc"]))
        db.execute("UPDATE appeals SET status = ?, reviewer_note = ?, resolved_at = ? WHERE ticket = ?",
                   (outcome, note, now_iso(), ticket))
        if outcome == "overturned":
            db.execute("UPDATE applications SET final_decision = 'approved' WHERE id = ?", (a["app_id"],))
        log(a["app_id"], "Human review closed", f"Credit officer · {user['display_name']}",
            f"Ticket {ticket} · decision {'overturned → approved' if outcome == 'overturned' else 'upheld'}")
        db.commit()
        return jsonify(ok=True, ticket=ticket, status=outcome)

    @app.get("/api/fairness")
    @security.require("staff")
    def fairness_report(user):
        return jsonify(fairness.report())

    return app
