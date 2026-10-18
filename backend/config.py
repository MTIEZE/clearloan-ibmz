"""ClearLoan back-end settings. Every value can be overridden with an environment variable."""
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # folder with the HTML pages
INSTANCE = Path(os.environ.get("CLEARLOAN_INSTANCE", ROOT / "instance"))
INSTANCE.mkdir(parents=True, exist_ok=True)


def _key_file(name: str, make) -> str:
    """Read a key from instance/<name>, creating it on first run. Never committed (see .gitignore)."""
    path = INSTANCE / name
    if not path.exists():
        path.write_text(make(), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def _fernet_key() -> str:
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


SECRET_KEY = os.environ.get("CLEARLOAN_SECRET_KEY") or _key_file("secret.key", lambda: secrets.token_hex(32))
DATA_KEY = os.environ.get("CLEARLOAN_DATA_KEY") or _key_file("data.key", _fernet_key)
DATABASE = os.environ.get("CLEARLOAN_DB", str(INSTANCE / "clearloan.sqlite3"))

SESSION_MINUTES = int(os.environ.get("CLEARLOAN_SESSION_MINUTES", 15))
LOCK_AFTER = int(os.environ.get("CLEARLOAN_LOCK_AFTER", 5))
LOCK_MINUTES = int(os.environ.get("CLEARLOAN_LOCK_MINUTES", 10))
APPROVAL_LIMIT = int(os.environ.get("CLEARLOAN_APPROVAL_LIMIT", 50))
COOKIE_SECURE = os.environ.get("CLEARLOAN_COOKIE_SECURE", "0") == "1"   # set to 1 behind HTTPS

# Optional local LLM (IBM Granite through Ollama on the same server). Empty = built-in templates.
OLLAMA_URL = os.environ.get("CLEARLOAN_OLLAMA_URL", "")
GRANITE_MODEL = os.environ.get("CLEARLOAN_GRANITE_MODEL", "granite3.3:2b")
GEMINI_MODEL = os.environ.get("CLEARLOAN_GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_KEY_FILE = INSTANCE / "gemini_api_key"
LLM_TIMEOUT = float(os.environ.get("CLEARLOAN_LLM_TIMEOUT", 25))

LANGUAGES = ("en", "ar", "ur", "hi", "fr")
