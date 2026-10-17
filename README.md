# ClearLoan

Team **Made To Rise** · IBM Z Datathon 2026 · Theme 2: *AI Secured – Innovation Without Exposure*

Private, fair and explainable loan decisions. Plain HTML, CSS and JavaScript on the front-end (no build step), a Python / Flask back-end, SQLite storage.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m backend
```

Then open http://localhost:8000. The first run creates the database, the encryption keys (in `instance/`, never commit them), two demo accounts and 48 sample applications, so the dashboards have data.

**Demo accounts (local only):**

| Role | Tab on the sign-in page | Email | Password |
|---|---|---|---|
| Applicant | Applicant | `demo@clearloan.test` | `ClearLoan-Demo-2026` |
| Bank staff | Bank staff | `auditor@clearloan.test` | `ClearLoan-Staff-2026` + a 6-digit code |

Applicants can also create their own account from the sign-in page.

**Signing in as bank staff.** Staff accounts use two-factor sign-in, so the form also asks for a 6-digit code. The `123 456` shown in the field is only an example. To get the real code:

1. Fill in the email and password first: the code changes every 30 seconds.
2. In a terminal, in the project folder, run the command below. Wait 2 to 3 seconds, do not press Ctrl+C.
   ```bash
   .venv\Scripts\python.exe -m backend totp auditor@clearloan.test    # macOS / Linux: .venv/bin/python
   ```
3. Type the 6 digits it prints and sign in right away. If the code is refused, run the command again for a new one.

Easier for a demo: add the key `JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP` (`DEMO_TOTP_SECRET` in `backend/seed.py`) to Google Authenticator or Microsoft Authenticator ("Enter a setup key", time based). The phone then always shows the current code.

After 5 wrong tries the account is locked for 10 minutes. To unlock it at once: `python -m backend unlock auditor@clearloan.test`.

To be signed in to both accounts at the same time, open the second one in a private window. In the same window, a new sign-in replaces the first one.

Other commands:

```bash
python -m backend seed --samples 100              # more demo data
python -m backend unlock EMAIL                    # clear failed sign-ins and the 10-minute lock
python -m backend add-staff jane@bank.ae "Jane"    # real staff account, prints the authenticator link
python -m backend run --host 0.0.0.0 --port 8000  # reachable from other machines (or set CLEARLOAN_HOST / CLEARLOAN_PORT)
python -m pytest backend/tests                    # back-end tests (pip install -r requirements-dev.txt)
```

**Front-end only (no back-end):** double-click `index.html`, or add `?mock=1` to any page URL. Fake data, same JSON contract. `?mock=0` switches back.

## Repository layout

```
*.html        the 6 pages (at the repo root: the Flask back-end serves them from here, see ROOT in backend/config.py)
assets/       css/style.css, js/ (api.js = every API call, config.js, mock.js = offline mode)
backend/      Flask app, privacy gateway, risk model, LLM explanations, fairness, tests
models/       trained model files (ML)
notebooks/    training and fairness notebooks (ML & Fairness)
instance/     created on first run: SQLite database + keys. Git-ignored, never commit it
```

`backend/model.py` and `backend/data/fairness_report.json` are placeholders until the ML and Fairness work replaces them. Never commit the LinuxONE `.pem` key or the Jupyter token.

## Pages

| File | Who | What |
|---|---|---|
| `index.html` | everyone | Sign in (applicant / bank staff with 6-digit code), create an applicant account |
| `apply.html` | applicant | Loan form, live "quick check" of the payment ratio, previous applications |
| `decision.html` | applicant | Decision, risk gauge, reasons, explanation in 5 languages, steps with real numbers, human review request and its status |
| `privacy.html` | applicant + staff | What the AI saw: masked identity, model input, prompt, audit log. Staff can search any application |
| `fairness.html` | staff | Offline fairness metrics (before/after mitigation, model A vs B) + live monitoring of decisions on this server |
| `reviews.html` | staff | Human review queue: approve the loan or keep the decision, with a message to the applicant |

Light and dark themes (follows the system, toggle in the header), keyboard and screen-reader friendly, works from 375 px wide, print-friendly decision page.

## Back-end (`backend/`)

| File | Role |
|---|---|
| `app.py` | Flask app: serves the pages and the `/api/*` routes, security headers, CSRF check |
| `security.py` | Password hashing (scrypt), lockout (5 tries → 10 min), TOTP two-factor for staff, 15-min sessions, role checks |
| `gateway.py` | Privacy gateway: identity encrypted with Fernet (AES), replaced by a token, masked, PII scan of every prompt, redaction of free text for staff |
| `model.py` | Explainable risk scorecard (two variants: full history / first-time borrower), exact per-feature contributions, counterfactuals ("up to AED X would be approved") |
| `llm.py` | Explanations and steps in English, Arabic, Urdu, Hindi and French. Uses IBM Granite through Ollama when configured, built-in templates otherwise |
| `fairness.py` | Offline report (`data/fairness_report.json`) + live approval rates by sex and age band |
| `service.py` | The pipeline: web app → gateway → model → LLM → gateway, and the JSON read models |
| `db.py` | SQLite schema, audit log |

**Pipeline for one application:** the identity is encrypted and swapped for `Applicant_XXXXXX` → the risk model gets financial data only (sex is kept apart, for the fairness audit) → the prompt is built from the token, decision and reasons, then scanned for personal data (the LLM call is blocked if anything is found) → the explanation comes back with the token, and the first name is put back only when the applicant reads it. Every step is written to the audit log.

**Use IBM Granite** (runs on the same server, nothing leaves it):

```bash
ollama pull granite3.3:2b
set CLEARLOAN_OLLAMA_URL=http://localhost:11434     # macOS / Linux: export ...
python -m backend
```

If the model is slow or returns bad output, the back-end falls back to the templates and says so in the audit log.

**Settings** (environment variables): `CLEARLOAN_SECRET_KEY`, `CLEARLOAN_DATA_KEY` (Fernet key), `CLEARLOAN_DB`, `CLEARLOAN_SESSION_MINUTES` (15), `CLEARLOAN_LOCK_AFTER` (5), `CLEARLOAN_LOCK_MINUTES` (10), `CLEARLOAN_APPROVAL_LIMIT` (50), `CLEARLOAN_COOKIE_SECURE=1` behind HTTPS, `CLEARLOAN_OLLAMA_URL`, `CLEARLOAN_GRANITE_MODEL`, `CLEARLOAN_HOST`, `CLEARLOAN_PORT`.

For production, run behind a WSGI server and HTTPS, for example `gunicorn "backend.app:create_app()"` on LinuxONE, set `CLEARLOAN_COOKIE_SECURE=1`, and replace the demo accounts.

## API contract (JSON)

All calls go through `assets/js/api.js`. State-changing calls must send JSON with the header `X-ClearLoan: 1` (CSRF protection). The server checks the session and role on every call; the front-end only hides pages. Errors look like `{ "ok": false, "error": "invalid", "field": "age", "message": "..." }`.

### Auth

```json
POST /api/login     { "email": "...", "password": "...", "role": "applicant | staff", "code": "123456" }
→ { "ok": true, "role": "applicant", "display_name": "Sara" }
→ { "ok": false, "error": "invalid", "attempts_left": 3 }  |  { "ok": false, "error": "locked", "minutes_left": 9 }

POST /api/register  { "email": "...", "password": "8+ chars", "display_name": "Sara" }  → 201 { "ok": true, "role": "applicant", ... }
GET  /api/me        → { "ok": true, "role": "...", "display_name": "...", "session_minutes": 15 } | { "ok": false }
POST /api/logout
```

### `POST /api/apply` (applicant)
```json
{
  "identity":  { "name": "...", "id_number": "...", "phone": "...", "email": "..." },
  "financial": { "loan_amount": 50000, "avg_bill": 3200, "avg_payment": 600, "age": 24,
                 "education": "university", "marriage": "single",
                 "credit_history": false, "pay_history": [] },
  "audit":     { "sex": "male" },
  "language":  "en | ar | ur | hi | fr"
}
```
Response (201), also returned by `GET /api/applications/<id>`:
```json
{
  "application_id": "CL-7F3A2B",
  "token": "Applicant_7F3A2B",
  "created_at": "2026-10-17T09:41:02.114Z",
  "latency_ms": 12,
  "model_used": "first_time_borrower | full_history",
  "display_name": "Ahmed",
  "request": { "loan_amount": 50000, "language": "en" },
  "model": {
    "decision": "approved | not_approved",
    "risk_score": 72, "limit": 50, "version": "scorecard-1.3",
    "top_reasons": [ { "feature": "payment_ratio", "value": 0.19, "impact": "high", "direction": "raises", "weight": 0.54,
                       "label": "Your monthly payments cover only 19% of your monthly bills" } ]
  },
  "final_decision": "approved | not_approved",
  "llm": { "explanation": "Hello Ahmed, ...", "explanation_en": "... or null", "steps": ["...", "...", "..."],
           "appeal_draft": "Dear ClearLoan team, ...", "language": "en", "engine": "IBM Granite (...) | ClearLoan explainer (templates)" },
  "appeal": null
}
```
Rules: `identity` never goes to the model or the LLM. `display_name` is the first name only, put back by the gateway at the end. For staff, `display_name` is `null`. `final_decision` differs from `model.decision` only when a credit officer overturned it.

### Other routes

| Route | Who | Returns |
|---|---|---|
| `GET /api/applications` | applicant: own · staff: all | `{ "items": [ { "application_id", "created_at", "loan_amount", "risk_score", "decision", "final_decision", "appeal_status", ... } ] }` |
| `GET /api/privacy/<id>` | applicant: own · staff | `token`, `identity_masked` (staff: name/phone/email `null`), `audit_only`, `model_input`, `prompt`, `pii_scan`, `engine`, `audit_log[] { ts, time, step, component, details }` |
| `POST /api/appeal/<id>` `{ "text" }` | applicant | `{ "ok": true, "ticket": "RV-1A2B3", "reviewer": "Credit officer", "eta_hours": 48, "status": "open" }` |
| `GET /api/reviews` | staff | Appeals with the model decision; names and contact details redacted from the text |
| `POST /api/reviews/<ticket>` `{ "outcome": "upheld \| overturned", "note" }` | staff | `{ "ok": true, "ticket", "status" }` |
| `GET /api/fairness` | staff | Offline `metrics`, `groups`, `models`, `method`, `dataset` + `live` (decisions, approval rate, gap, ratio; groups under 10 decisions are left out of gaps and ratios) |
| `GET /api/health` | everyone | Model version and LLM engine |

## Security notes

- Passwords hashed with scrypt; wrong email and wrong password take the same time and give the same answer.
- Lockout after 5 failures for 10 minutes, counted per email (also for unknown emails, so accounts can't be discovered).
- Staff need a TOTP code (RFC 6238). Sessions: HttpOnly, SameSite=Strict cookie, new session on sign-in, 15 minutes of inactivity (checked by the server).
- Identity encrypted at rest (Fernet); only the gateway can read it. Kept in clear: the first name (to greet the applicant) and a masked copy (`Ahmed K•••`). The prompt is scanned before every LLM call.
- Strict Content Security Policy (scripts from this server only), `X-Frame-Options: DENY`, `no-referrer`, `no-store` on API answers.
- Only the HTML pages and `assets/` are served; the back-end source and `instance/` keys are not.
- All dynamic text is escaped before display (`CL.esc`) to block XSS. Raw identity is never stored in the browser.

## Open-source resources

- IBM Plex and Noto Sans Devanagari fonts (SIL Open Font License) via Google Fonts. Icons drawn in the Lucide style.
- Flask (BSD), cryptography (Apache 2.0 / BSD).
