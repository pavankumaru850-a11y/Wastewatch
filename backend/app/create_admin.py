"""create_admin.py -- create (or promote) an ADMIN account. Works in production, unlike app.seed.

    python -m app.create_admin                       (prompts)
    python -m app.create_admin --email a@b.org --name "Ada"   (password is always prompted, never a flag,
                                                            so it does not end up in shell history)
Non-interactive (CI/provisioning): set ADMIN_PASSWORD in the environment.
"""
import argparse
import getpass
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from .database import SessionLocal  # noqa: E402
from .migrate import run_migrations  # noqa: E402
from .models import RoleEnum, User  # noqa: E402
from .utils.security import hash_password  # noqa: E402


def create_admin(email: str, name: str, password: str) -> str:
    email = email.strip().lower()
    if "@" not in email or len(password) < 8:
        raise ValueError("A valid email and a password of at least 8 characters are required.")
    run_migrations()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.role, user.is_active = RoleEnum.ADMIN, True
            user.password_hash = hash_password(password)
            action = "promoted to ADMIN (password reset)"
        else:
            db.add(User(name=name or "Administrator", email=email, password_hash=hash_password(password), role=RoleEnum.ADMIN))
            action = "created"
        db.commit()
        return action
    finally:
        db.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--email")
    p.add_argument("--name", default="")
    a = p.parse_args(argv)
    email = a.email or input("Admin email: ")  # required
    name = a.name or (input("Full name: ") if sys.stdin.isatty() else "")
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password (8+ characters): ")
    try:
        print(f"{email}: {create_admin(email, name, password)}")
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
