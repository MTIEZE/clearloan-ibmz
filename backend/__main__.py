"""Command line: `python -m backend [run|seed|totp EMAIL|add-staff EMAIL NAME]`."""
import argparse
import getpass
import os

from . import config, security
from .app import create_app
from .db import get_db


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m backend", description="ClearLoan back-end")
    sub = p.add_subparsers(dest="cmd")
    run = sub.add_parser("run", help="start the web server (default)")
    run.add_argument("--host", default=os.environ.get("CLEARLOAN_HOST", "127.0.0.1"))
    run.add_argument("--port", type=int, default=int(os.environ.get("CLEARLOAN_PORT", 8000)))
    run.add_argument("--debug", action="store_true")
    seed = sub.add_parser("seed", help="create demo accounts and sample applications")
    seed.add_argument("--samples", type=int, default=48)
    totp = sub.add_parser("totp", help="print the current 6-digit code of a staff account")
    totp.add_argument("email")
    staff = sub.add_parser("add-staff", help="create a staff account with two-factor sign-in")
    staff.add_argument("email")
    staff.add_argument("name")
    args = p.parse_args()

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
            print(security.totp(row["totp_secret"]) if row else "No staff account with this email.")
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
            print(f"ClearLoan on http://{getattr(args, 'host', '127.0.0.1')}:{getattr(args, 'port', 8000)} · explanations: {llm}")
    if args.cmd in (None, "run"):
        app.run(host=getattr(args, "host", "127.0.0.1"), port=getattr(args, "port", 8000),
                debug=getattr(args, "debug", False))


if __name__ == "__main__":
    main()
