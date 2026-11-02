"""migrate.py -- tiny additive migration. SQLAlchemy's create_all() creates
missing TABLES but never adds new COLUMNS to tables that already exist, so
an existing wastewatch.db from the previous version would break. This adds
any model column that is missing (ALTER TABLE ... ADD COLUMN). It never
drops or rewrites data. Also creates the new indexes."""
import logging
from sqlalchemy import inspect, text

from . import models  # noqa: F401  (registers every table on Base.metadata)
from .database import Base, engine

log = logging.getLogger("wastewatch.migrate")


def run_migrations() -> list[str]:
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    added = []
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                coltype = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {coltype}'))
                added.append(f"{table.name}.{col.name}")
    if engine.dialect.name == "postgresql":  # new enum member: PostgreSQL enums are real types
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text("ALTER TYPE reportstatus ADD VALUE IF NOT EXISTS 'NOT_WASTE'"))
        except Exception as e:  # noqa: BLE001
            log.warning("could not add NOT_WASTE to enum reportstatus: %s", e)
    for name in added:
        log.info("migration: added column %s", name)
    # create any missing indexes on existing tables
    for table in Base.metadata.sorted_tables:
        for idx in table.indexes:
            try:
                idx.create(bind=engine, checkfirst=True)
            except Exception as e:  # noqa: BLE001
                log.warning("index %s skipped: %s", idx.name, e)
    return added
