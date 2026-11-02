"""
database.py -- SQLAlchemy engine and session setup.

Uses SQLite by default (DATABASE_URL unset). To move to Postgres for
production, set DATABASE_URL=postgresql://user:pass@host:5432/dbname
in .env -- nothing else in the app needs to change, since every model
and query goes through this same engine/session.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def _normalize(url: str) -> str:
    """Use the driver we ship (psycopg2-binary). Newer SQLAlchemy defaults plain 'postgresql://' to psycopg v3,
    and Heroku-style 'postgres://' is not understood at all."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


DATABASE_URL = _normalize(os.environ.get("DATABASE_URL", "sqlite:///./wastewatch.db"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
