"""seed.py -- DEVELOPMENT-ONLY demo accounts.

    python -m app.seed

Passwords come from the environment (SEED_ADMIN_PASSWORD, SEED_STAFF_PASSWORD,
SEED_CITIZEN_PASSWORD); if unset a random one is generated and printed ONCE.
Refuses to run when APP_ENV=production. Safe to re-run (skips existing users).
"""
import os
import secrets
import sys

from dotenv import load_dotenv

load_dotenv()

from .database import SessionLocal  # noqa: E402
from .migrate import run_migrations  # noqa: E402
from .models import RoleEnum, User  # noqa: E402
from .utils.security import hash_password  # noqa: E402

ACCOUNTS = [("admin@wastewatch.dev", "Demo Admin", RoleEnum.ADMIN, "SEED_ADMIN_PASSWORD"),
            ("staff@wastewatch.dev", "Demo Staff", RoleEnum.STAFF, "SEED_STAFF_PASSWORD"),
            ("citizen@wastewatch.dev", "Demo Citizen", RoleEnum.CITIZEN, "SEED_CITIZEN_PASSWORD")]


def main() -> None:
    if os.environ.get("APP_ENV", "development") == "production":
        sys.exit("Refusing to seed demo accounts in production.")
    run_migrations()
    db = SessionLocal()
    try:
        for email, name, role, env_key in ACCOUNTS:
            if db.query(User).filter(User.email == email).first():
                print(f"exists : {email}")
                continue
            pw = os.environ.get(env_key) or secrets.token_urlsafe(9)
            db.add(User(name=name, email=email, password_hash=hash_password(pw), role=role))
            db.commit()
            print(f"created: {email:28s} role={role.value:8s} password={pw}   (DEVELOPMENT ONLY)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
