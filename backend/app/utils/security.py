"""utils/security.py -- password hashing and JWT encode/decode. No plaintext
passwords are ever stored or compared."""
import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

DEV_DEFAULT_KEY = "dev-only-change-me-in-.env"
SECRET_KEY = os.environ.get("SECRET_KEY") or DEV_DEFAULT_KEY


def validate_secret(app_env: str, key: str) -> str | None:
    """Returns a warning string for development, raises in production. A guessable signing key lets anyone
    mint an admin token, so production must never start with the built-in default or a short key."""
    weak = key == DEV_DEFAULT_KEY or len(key) < 32
    if not weak:
        return None
    msg = ("SECRET_KEY is missing or too short (need 32+ random characters). "
           'Generate one: python -c "import secrets; print(secrets.token_urlsafe(48))"')
    if app_env == "production":
        raise RuntimeError(msg + " Refusing to start in production.")
    return msg + " Using an insecure development key."
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
