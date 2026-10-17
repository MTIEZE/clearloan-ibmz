"""Command line: `python -m backend [run|seed|totp EMAIL|unlock EMAIL|add-staff EMAIL NAME]`."""
import argparse
import getpass
import os
import time

from . import config, security
from .app import create_app
from .db import get_db


def main() -> None:
    host = os.environ.get("CLEARLOAN_HOST", "127.0.0.1")
    port = int(os.environ.get("CLEARLOAN_PORT", 8000))
    p = argparse.ArgumentParser(prog="python -m backend", description="ClearLoan back-end")
    sub = p.add_subparsers(dest="cmd")
    run = sub.add_parser("run", help="start the web server (default)")
    run.add_argument("--host", default=host)
    run.add_argument("--port", type=int, default=port)
    run.add_argument("--debug", action="store_true")
    seed = sub.add_parser("seed", help="create demo accounts and sample applications")
    seed.add_argument("--samples", type=int, default=48)
    totp = sub.add_parser("totp", help="print the current 6-digit code of a staff account")
    totp.add_argument("email")
    unlock = sub.add_parser("unlock", help="clear failed sign-ins and the lock of an account")
    unlock.add_argument("email")
    staff = sub.add_parser("add-staff", help="create a staff account with two-factor sign-in")
    staff.add_argument("email")
    staff.add_argument("name")
    args = p.parse_args()
    # Without the `run` word the sub-command defaults are not applied, so fall back to the settings here
    host, port = getattr(args, "host", host), getattr(args, "port", port)

    app = create_app()
    with app.app_context():
        from . import seed as demo
        db = get_db()
        if args.cmd == "seed":
            demo.seed_accounts()
            print(f"Demo accounts ready. {demo.seed_samples(args.samples)} sample applications added.")
        elif args.cmd == "totp":
            row = db.execute("SELECT totp_secret FROM users WHERE email = ? AND role = 'staff'",
                             (args.email.lower(),)).fetchone()
            left = 30 - int(time.time()) % 30
            print(f"{security.totp(row['totp_secret'])}  (changes in {left} s)" if row else "No staff account with this email.")
        elif args.cmd == "unlock":
            security.clear_failures(args.email.strip().lower())
            db.commit()
            print(f"{args.email} can sign in again.")
        elif args.cmd == "add-staff":
            password = getpass.getpass("Password (8+ characters): ")
            if len(password) < 8:
                raise SystemExit("Password too short.")
            secret = security.new_totp_secret()
            demo.add_user(args.email.lower(), password, args.name, role="staff", totp_secret=secret)
            print("Staff account created. Add this to an authenticator app:\n " + security.totp_uri(secret, args.email))
        else:
            if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                demo.seed_accounts()
                n = demo.seed_samples()
                print(f"First run: demo accounts and {n} sample applications created (see backend/seed.py).")
            llm = f"IBM Granite via Ollama ({config.GRANITE_MODEL})" if config.OLLAMA_URL else "built-in templates"
            print(f"ClearLoan on http://{host}:{port} · explanations: {llm}")
    if args.cmd in (None, "run"):
        app.run(host=host, port=port, debug=getattr(args, "debug", False))


if __name__ == "__main__":
    main()
