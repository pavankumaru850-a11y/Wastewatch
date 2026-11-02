"""bootstrap.py -- runs before the API starts in the hosted (Docker) setup.

If ADMIN_EMAIL and ADMIN_PASSWORD are set, that admin account is created (or its password reset) so you can log in
to the dashboard on a server where you have no shell. Never raises: a mistake here must not stop the API from starting.
"""
import os

from .create_admin import create_admin


def main() -> int:
    email, password = os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD")
    if not (email and password):
        print("bootstrap: ADMIN_EMAIL / ADMIN_PASSWORD not set, skipping admin creation")
        return 0
    try:
        print(f"bootstrap: {email}: {create_admin(email, os.environ.get('ADMIN_NAME', 'Administrator'), password)}")
    except Exception as e:  # noqa: BLE001
        print(f"bootstrap: could not create the admin: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
