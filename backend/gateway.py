"""Privacy gateway: identity is encrypted, replaced by a token, and checked for before any AI call."""
import json
import re
import secrets

from cryptography.fernet import Fernet

from . import config

_fernet = Fernet(config.DATA_KEY.encode())


def new_ids() -> tuple[str, str]:
    """Application id and pseudonymous token share a random suffix: CL-7F3A2B / Applicant_7F3A2B."""
    suffix = secrets.token_hex(3).upper()
    return f"CL-{suffix}", f"Applicant_{suffix}"


def encrypt_identity(identity: dict) -> bytes:
    return _fernet.encrypt(json.dumps(identity).encode())


def decrypt_identity(blob: bytes) -> dict:
    return json.loads(_fernet.decrypt(blob))


def _dots(n: int) -> str:
    return "•" * max(0, n)


def mask_email(email: str) -> str:
    user, _, domain = email.partition("@")
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    return user[:1] + _dots(4) + "@" + _dots(5) + (f".{tld}" if tld else "")


def mask_identity(identity: dict) -> dict:
    name = identity["name"].split()
    first, last = name[0], (name[1] if len(name) > 1 else "")
    id_number = identity["id_number"]
    phone = identity["phone"]
    return {
        "name": first + (f" {last[0]}•••" if last else ""),
        "id_number": id_number[:4] + re.sub(r"[A-Za-z0-9]", "•", id_number[4:]),
        "phone": phone[:4] + re.sub(r"\d", "•", phone[4:]),
        "email": mask_email(identity["email"]),
    }


# Generic patterns, on top of the applicant's own values
_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),                       # email
    re.compile(r"\b784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d\b"),           # Emirates ID
    re.compile(r"\+?\d[\d\s-]{7,}\d"),                             # phone-like runs of 9+ digits
]


def pii_scan(text: str, identity: dict) -> list[str]:
    """Return the kinds of personal data found in `text` (empty list = safe to send)."""
    found = []
    lowered = text.lower()
    for part in identity["name"].split():
        if len(part) >= 3 and re.search(rf"\b{re.escape(part.lower())}\b", lowered):
            found.append("name")
            break
    digits = re.sub(r"\D", "", text)
    for kind in ("id_number", "phone"):
        value = re.sub(r"\D", "", identity.get(kind, ""))
        if len(value) >= 6 and value in digits:
            found.append(kind)
    if identity["email"].lower() in lowered:
        found.append("email")
    for pattern, kind in zip(_PATTERNS, ("email", "id_number", "phone")):
        for match in pattern.finditer(text):
            if kind != "phone" or len(re.sub(r"\D", "", match.group())) >= 9:
                found.append(kind)
                break
    return sorted(set(found))


def redact(text: str, identity: dict) -> str:
    """Remove the applicant's own identity values (and anything that looks like contact data) from free text."""
    for kind in ("email", "id_number", "phone"):
        value = identity.get(kind, "").strip()
        if value:
            text = re.sub(re.escape(value), f"[{kind.replace('_', ' ')}]", text, flags=re.I)
    for part in identity["name"].split():
        if len(part) >= 2:
            text = re.sub(rf"\b{re.escape(part)}\b", "[name]", text, flags=re.I)
    text = _PATTERNS[0].sub("[email]", text)
    text = _PATTERNS[1].sub("[id number]", text)
    return _PATTERNS[2].sub(lambda m: "[phone]" if len(re.sub(r"\D", "", m.group())) >= 9 else m.group(), text)


def restore_name(text: str, token: str, first_name: str) -> str:
    """Last gateway step: put the first name back, for the applicant's eyes only."""
    return text.replace(token, first_name)
