"""Authentication, sessions, lockout, two-factor codes and role checks."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import config
from .db import get_db

# A fixed hash used when the email is unknown, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def hash_password(password: str) -> str:
    return generate_password_hash(password)          # scrypt, salted


# ---------- TOTP (RFC 6238), compatible with Google Authenticator, Microsoft Authenticator, etc.

def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp(secret: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    counter = int((at if at is not None else time.time()) // step)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 10 ** digits
    return str(code).zfill(digits)


def verify_totp(secret: str | None, code: str | None) -> bool:
    if not secret or not code:
        return False
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != 6:
        return False
    t = time.time()
    return any(hmac.compare_digest(totp(secret, t + drift * 30), code) for drift in (-1, 0, 1))


def totp_uri(secret: str, email: str) -> str:
    return f"otpauth://totp/ClearLoan:{email}?secret={secret}&issuer=ClearLoan"


# ---------- Lockout

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def lock_status(email: str) -> int:
    """Minutes left on a lock, or 0 when the account is not locked."""
    row = get_db().execute("SELECT locked_until FROM login_attempts WHERE email = ?", (email,)).fetchone()
    if not row or not row["locked_until"]:
        return 0
    left = datetime.fromisoformat(row["locked_until"].replace("Z", "+00:00")) - _utcnow()
    return max(0, int(-(-left.total_seconds() // 60)))


def record_failure(email: str) -> int:
    """Count a failed sign-in. Returns attempts left (0 means the account is now locked)."""
    db = get_db()
    row = db.execute("SELECT failures FROM login_attempts WHERE email = ?", (email,)).fetchone()
    failures = (row["failures"] if row else 0) + 1
    locked_until = None
    if failures >= config.LOCK_AFTER:
        locked_until = (_utcnow() + timedelta(minutes=config.LOCK_MINUTES)).isoformat()
        failures = 0
    db.execute("INSERT INTO login_attempts (email, failures, locked_until) VALUES (?, ?, ?) "
               "ON CONFLICT(email) DO UPDATE SET failures = excluded.failures, locked_until = excluded.locked_until",
               (email, failures, locked_until))
    return 0 if locked_until else config.LOCK_AFTER - failures


def clear_failures(email: str) -> None:
    get_db().execute("DELETE FROM login_attempts WHERE email = ?", (email,))


def check_credentials(email: str, password: str, role: str, code: str | None):
    """Return the user row when email, password, role and (for staff) the 6-digit code all match."""
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    ok_password = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password or "")
    if not user or not ok_password or user["role"] != role:
        return None
    if role == "staff" and not verify_totp(user["totp_secret"], code):
        return None
    return user


# ---------- Sessions

def start_session(user) -> None:
    session.clear()                                  # new session id on every sign-in
    session["uid"] = user["id"]
    session["role"] = user["role"]
    session["name"] = user["display_name"]
    session["last"] = time.time()
    session["csrf"] = secrets.token_urlsafe(24)


def current_user():
    """The signed-in user as a dict, or None. Ends the session after inactivity (server side)."""
    if "uid" not in session:
        return None
    if time.time() - session.get("last", 0) > config.SESSION_MINUTES * 60:
        session.clear()
        return None
    session["last"] = time.time()
    return {"id": session["uid"], "role": session["role"], "display_name": session["name"]}


def require(*roles):
    """Route decorator: signed-in user with one of these roles. Passes the user as `user`."""
    def wrap(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify(ok=False, error="unauthorized"), 401
            if roles and user["role"] not in roles:
                return jsonify(ok=False, error="forbidden"), 403
            return fn(*args, user=user, **kwargs)
        return inner
    return wrap


def csrf_ok() -> bool:
    """State-changing calls must be JSON and carry our header: a cross-site form cannot do both."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True
    return request.is_json and request.headers.get("X-ClearLoan") == "1"


SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
